import pathlib
import time
from functools import partial

import dill as pickle
import event_model
from intake_bluesky.in_memory import BlueskyInMemoryCatalog
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.parametertree.parameterTypes import ListParameter
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from xicam.core import msg
from xicam.core.data import NonDBHeader
from xicam.gui.widgets.imageviewmixins import PolygonROI
from xicam.gui.widgets.tabview import TabView
from xicam.plugins import GUILayout, GUIPlugin
from xicam.plugins import manager as pluginmanager
from xicam.SAXS.widgets.SAXSViewerPlugin import SAXSViewerPluginBase

from .widgets.views import (CorrelationView, FileSelectionView, OneTimeView,
                            TwoTimeView)
from .workflows import FourierAutocorrelator, OneTime, TwoTime


class XPCSViewerPlugin(PolygonROI, SAXSViewerPluginBase):
    pass


class XPCSProcessor(ParameterTree):
    def __init__(self, *args, **kwargs):
        super(XPCSProcessor, self).__init__()
        self._paramName = 'Algorithm'
        self._name = 'XPCS Processor'
        self.workflow = None
        self.param = None
        self._workflows = dict()

        self.listParameter = ListParameter(name=self._paramName,
                                           values={'':''},
                                           value='')

        self.param = Parameter(children=[self.listParameter], name=self._name)
        self.setParameters(self.param, showTop=False)

    def update(self, *_):
        for child in self.param.childs[1:]:
            child.remove()

        self.workflow = self._workflows.get(self.listParameter.value().name, self.listParameter.value()())
        self._workflows[self.workflow.name] = self.workflow
        for process in self.workflow.processes:
            self.param.addChild(process.parameter)


class OneTimeProcessor(XPCSProcessor):
    def __init__(self, *args, **kwargs):
        super(OneTimeProcessor, self).__init__()
        self._name = '1-Time Processor'
        self.listParameter.setLimits(OneTimeAlgorithms.algorithms())
        self.listParameter.setValue(OneTimeAlgorithms.algorithms()[OneTimeAlgorithms.default()])

        self.update()
        self.listParameter.sigValueChanged.connect(self.update)


class TwoTimeProcessor(XPCSProcessor):
    def __init__(self, *args, **kwargs):
        super(TwoTimeProcessor, self).__init__()
        self._name = '2-Time Processor'
        self.listParameter.setLimits(TwoTimeAlgorithms.algorithms())
        self.listParameter.setValue(TwoTimeAlgorithms.algorithms()[TwoTimeAlgorithms.default()])

        self.update()
        self.listParameter.sigValueChanged.connect(self.update)


class ProcessingAlgorithms:
    """
    Convenience class to get the available algorithms that can be used for
    one-time and two-time correlations.
    """
    @staticmethod
    def algorithms():
        return {
            TwoTimeAlgorithms.name: TwoTimeAlgorithms.algorithms(),
            OneTimeAlgorithms.name: OneTimeAlgorithms.algorithms()
        }


class TwoTimeAlgorithms(ProcessingAlgorithms):
    name = '2-Time Algorithms'
    @staticmethod
    def algorithms():
        return {TwoTime.name: TwoTime}

    @staticmethod
    def default():
        return TwoTime.name


class OneTimeAlgorithms(ProcessingAlgorithms):
    name = '1-Time Algorithms'
    @staticmethod
    def algorithms():
        return {OneTime.name: OneTime,
                FourierAutocorrelator.name: FourierAutocorrelator}

    @staticmethod
    def default():
        return OneTime.name


class XPCS(GUIPlugin):
    name = 'XPCS'

    def __init__(self):
        self.catalog = BlueskyInMemoryCatalog()

        # XPCS data model
        self.resultsmodel = QStandardItemModel()

        # Input (raw) data model
        self.headermodel = QStandardItemModel()
        self.selectionmodel = QItemSelectionModel(self.headermodel)

        # Widgets
        self.calibrationsettings = pluginmanager.getPluginByName('xicam.SAXS.calibration',
                                                                 'SettingsPlugin').plugin_object
        self.processor = XPCSProcessor()

        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.addAction('Process', self.process)

        # Setup TabViews
        self.rawtabview = TabView(self.headermodel,
                                  widgetcls=XPCSViewerPlugin,
                                  selectionmodel=self.selectionmodel,
                                  bindings=[(self.calibrationsettings.sigGeometryChanged, 'setGeometry')],
                                  geometry=self.getAI)

        # Setup correlation views
        self.twotimeview = TwoTimeView()
        self.twotimefileselection = FileSelectionView(self.headermodel, self.selectionmodel)
        self.twotimeprocessor = TwoTimeProcessor()
        self.twotimetoolbar = QToolBar()
        self.twotimetoolbar.addAction('Process', self.processTwoTime)
        self.onetimeview = OneTimeView()
        self.onetimefileselection = FileSelectionView(self.headermodel, self.selectionmodel)
        self.onetimeprocessor = OneTimeProcessor()
        self.onetimetoolbar = QToolBar()
        self.onetimetoolbar.addAction('Process', self.processOneTime)
        self.onetimetoolbar.addAction('Figure', self.onetimeview.createFigure)

        self.placeholder = QLabel('correlation parameters')

        self.stages = {'Raw': GUILayout(self.rawtabview,
                                        # top=self.toolbar,
                                        right=self.calibrationsettings.widget),
                       '2-Time Correlation': GUILayout(self.twotimeview,
                                                       top=self.twotimetoolbar,
                                                       right=self.twotimefileselection,
                                                       rightbottom=self.twotimeprocessor,
                                                       bottom=self.placeholder),
                       '1-Time Correlation': GUILayout(self.onetimeview,
                                                       top=self.onetimetoolbar,
                                                       right=self.onetimefileselection,
                                                       rightbottom=self.onetimeprocessor,
                                                       bottom=self.placeholder)
                       }

        # TODO -- improve result caching
        self._results = []

        super(XPCS, self).__init__()

    def appendHeader(self, header: NonDBHeader, **kwargs):
        item = QStandardItem(header.startdoc.get('sample_name', '????'))
        item.header = header
        self.headermodel.appendRow(item)
        self.selectionmodel.reset()
        self.selectionmodel.setCurrentIndex(self.headermodel.index(self.headermodel.rowCount() - 1, 0),
                                            QItemSelectionModel.Rows)
        self.headermodel.dataChanged.emit(QModelIndex(), QModelIndex())

        paths = header.startdoc.get('paths')
        for path in paths:
            if path and pathlib.Path(path).suffix == '.hdf':
                startItem = QStandardItem(header.startdoc.get('sample_name', '??'))
                eventlist = header.eventdocs
                for event in eventlist:
                    # repr(event['data']['name']
                    eventItem = QStandardItem(event['data']['name'])
                    eventItem.setData(event, Qt.UserRole)
                    eventItem.setCheckable(True)
                    startItem.appendRow(eventItem)
                # TODO -- properly add to view (one-time or 2-time, etc.)
                self.onetimeview.model.invisibleRootItem().appendRow(startItem)

    def getAI(self):
        return None

    def currentheader(self):
        return self.headermodel.itemFromIndex(self.selectionmodel.currentIndex()).header

    def currentheaders(self):
        selected_indices = self.selectionmodel.selectedIndexes()
        headers = []
        for model_index in selected_indices:
            headers.append(self.headermodel.itemFromIndex(model_index).header)
        return headers

    def processOneTime(self):
        self.process(self.onetimeprocessor,
                     callback_slot=partial(self.saveResult, fileSelectionView=self.onetimefileselection),
                     finished_slot=partial(self.createDocument, view=self.onetimeview))

    def processTwoTime(self):
        self.process(self.twotimeprocessor,
                     callback_slot=partial(self.saveResult, fileSelectionView=self.twotimefileselection),
                     finished_slot=partial(self.createDocument, view=self.twotimeview))

    def process(self, processor: XPCSProcessor, **kwargs):
        if processor:
            workflow = processor.workflow

            data = [header.meta_array() for header in self.currentheaders()]
            currentWidget = self.rawtabview.currentWidget()
            labels = [currentWidget.poly_mask()] * len(data)
            num_levels = [1] * len(data)

            num_bufs = []
            for i, _ in enumerate(data):
                shape = data[i].shape[0]
                # multi_tau_corr requires num_bufs to be even
                if shape % 2:
                    shape += 1
                num_bufs.append(shape)

            if kwargs.get('callback_slot'):
                callback_slot = kwargs['callback_slot']
            else:
                callback_slot = self.saveResult
            if kwargs.get('finished_slot'):
                finished_slot = kwargs['finished_slot']
            else:
                finished_slot = self.createDocument

            workflow_pickle = None# pickle.dumps(workflow)
            workflow.execute_all(None,
                                 data=data,
                                 labels=labels,
                                 num_levels=num_levels,
                                 num_bufs=num_bufs,
                                 callback_slot=callback_slot,
                                 finished_slot=partial(finished_slot,
                                                       header=self.currentheader(),
                                                       roi=repr(currentWidget),
                                                       workflow=workflow_pickle))
            # TODO -- should header be passed to callback_slot
            # (callback slot handle can handle multiple data items in data list)

    def saveResult(self, result, fileSelectionView=None):
        if fileSelectionView:
            data = dict()
            if not fileSelectionView.correlationname.displayText():
                data['name'] = fileSelectionView.correlationname.placeholderText()
            else:
                data['name'] = fileSelectionView.correlationname.displayText()
            data['result'] = result

            self._results.append(data)

    def createDocument(self, view: CorrelationView, header, roi, workflow):
        self.catalog.upsert(self._createDocument, (self._results, header, roi, workflow), {})
        # TODO -- make sure that this works for multiple selected series to process
        key = list(self.catalog)[-1]

        parentItem = QStandardItem(self._results[-1]['name'])
        for name, doc in self.catalog[key].read_canonical():
            if name == 'event':
                resultsmodel = view.model
                # item = QStandardItem(doc['data']['name'])  # TODO -- make sure passed data['name'] is unique in model -> CHECK HERE
                item = QStandardItem(repr(doc['data']['name']))
                item.setData(doc, Qt.UserRole)
                item.setCheckable(True)
                parentItem.appendRow(item)
                selectionModel = view.selectionmodel
                selectionModel.reset()
                selectionModel.setCurrentIndex(
                    resultsmodel.index(resultsmodel.rowCount() - 1, 0), QItemSelectionModel.Rows)
                selectionModel.select(selectionModel.currentIndex(), QItemSelectionModel.SelectCurrent)
        resultsmodel.appendRow(parentItem)
        self._results = []

    def _createDocument(self, results, header, roi, workflow):
        timestamp = time.time()

        run_bundle = event_model.compose_run()
        yield 'start', run_bundle.start_doc

        # TODO -- make sure g2_err is calculated and added to internal process documents
        # TODO -- make sure workflow pickles, or try dill / cloudpickle
        source = 'Xi-cam'

        peek_result = results[0]['result']
        g2_shape = peek_result['g2'].value.shape[0]
        import numpy as np
        g2_err = np.zeros(g2_shape)
        g2_err_shape = g2_shape
        lag_steps_shape = peek_result['lag_steps'].value.shape[0]
        workflow = []
        workflow_shape = len(workflow)

        reduced_data_keys = {
            'g2': {'source': source, 'dtype': 'number', 'shape': [g2_shape]},
            'g2_err': {'source': source, 'dtype': 'number', 'shape': [g2_err_shape]},
            'lag_steps': {'source': source, 'dtype': 'number', 'shape': [lag_steps_shape]},
            'name': {'source': source, 'dtype': 'string', 'shape': []}, # todo -- shape
             'workflow': {'source': source, 'dtype': 'string', 'shape': [workflow_shape]}
         }
        reduced_stream_name = 'reduced'
        reduced_stream_bundle = run_bundle.compose_descriptor(data_keys=reduced_data_keys,
                                                              name=reduced_stream_name)
        yield 'descriptor', reduced_stream_bundle.descriptor_doc

        # todo -- peek frame shape
        frame_data_keys = {'frame': {'source': source, 'dtype': 'number', 'shape': []}}
        frame_stream_name = 'primary'
        frame_stream_bundle = run_bundle.compose_descriptor(data_keys=frame_data_keys,
                                                            name=frame_stream_name)
        yield 'descriptor', frame_stream_bundle.descriptor_doc

        # TODO -- repr the ROI(s) from the image
        name = repr('a')

        # todo -- store only paths? store the image data itself (memory...)
        # frames = header.startdoc['paths']
        frames = []
        for frame in frames:
            yield 'event', frame_stream_bundle.compose_event(
                data={frame},
                timestamps={timestamp}
            )

        for result in results:
            yield 'event', reduced_stream_bundle.compose_event(
                data={'g2': result['result']['g2'].value,
                      'g2_err': g2_err,
                      'lag_steps': result['result']['lag_steps'].value,
                      'name': roi,  # TODO update to roi
                      'workflow': workflow},
                timestamps={'g2': timestamp,
                            'g2_err': timestamp,
                            'lag_steps': timestamp,
                            'name': timestamp,
                            'workflow': workflow}
            )

        yield 'stop', run_bundle.compose_stop()
