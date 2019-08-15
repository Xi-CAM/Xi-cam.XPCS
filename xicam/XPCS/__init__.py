import pathlib
import time
from functools import partial

import cloudpickle as pickle
import event_model
from intake_bluesky.in_memory import BlueskyInMemoryCatalog
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.parametertree.parameterTypes import ListParameter
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from xicam.core import msg
from xicam.core.data import NonDBHeader
from xicam.gui import static
from xicam.gui.widgets.imageviewmixins import PolygonROI
from xicam.gui.widgets.ROI import BetterROI
from xicam.gui.widgets.tabview import TabView
from xicam.plugins import GUILayout, GUIPlugin
from xicam.plugins import manager as pluginmanager
from xicam.SAXS.widgets.SAXSViewerPlugin import SAXSViewerPluginBase

from .widgets.views import CorrelationView, FileSelectionView, OneTimeView, TwoTimeView
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
        self.resultsModel = QStandardItemModel()

        # Input (raw) data model
        self.headerModel = QStandardItemModel()
        self.selectionModel = QItemSelectionModel(self.headerModel)

        # Widgets
        self.calibrationSettings = pluginmanager.getPluginByName('xicam.SAXS.calibration',
                                                                 'SettingsPlugin').plugin_object

        # Setup TabViews
        self.rawTabView = TabView(self.headerModel,
                                  widgetcls=XPCSViewerPlugin,
                                  selectionmodel=self.selectionModel,
                                  bindings=[(self.calibrationSettings.sigGeometryChanged, 'setGeometry')],
                                  geometry=self.getAI)

        # Setup correlation views
        self.twoTimeView = TwoTimeView()
        self.twoTimeFileSelection = FileSelectionView(self.headerModel, self.selectionModel)
        self.twoTimeProcessor = TwoTimeProcessor()
        self.twoTimeToolBar = QToolBar()
        self.twoTimeToolBar.addAction(QIcon(static.path('icons/run.png')), 'Process', self.processTwoTime)
        self.twoTimeToolBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.oneTimeView = OneTimeView()
        self.oneTimeFileSelection = FileSelectionView(self.headerModel, self.selectionModel)
        self.oneTimeProcessor = OneTimeProcessor()
        self.oneTimeToolBar = QToolBar()
        self.oneTimeToolBar.addAction(QIcon(static.path('icons/run.png')), 'Process', self.processOneTime)
        self.oneTimeToolBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # self.placeholder = QLabel('correlation parameters')

        self.stages = {'Raw': GUILayout(self.rawTabView,
                                        right=self.calibrationSettings.widget),
                       '2-Time Correlation': GUILayout(self.twoTimeView,
                                                       top=self.twoTimeToolBar,
                                                       right=self.twoTimeFileSelection,
                                                       rightbottom=self.twoTimeProcessor,),
                                                       # bottom=self.placeholder),
                       '1-Time Correlation': GUILayout(self.oneTimeView,
                                                       top=self.oneTimeToolBar,
                                                       right=self.oneTimeFileSelection,
                                                       rightbottom=self.oneTimeProcessor,)
                                                       # bottom=self.placeholder)
                       }

        # TODO -- improve result caching
        self._results = []

        super(XPCS, self).__init__()

    def appendHeader(self, header: NonDBHeader, **kwargs):
        item = QStandardItem(header.startdoc.get('sample_name', '????'))
        item.header = header
        self.headerModel.appendRow(item)
        self.selectionModel.reset()
        self.selectionModel.setCurrentIndex(self.headerModel.index(self.headerModel.rowCount() - 1, 0),
                                            QItemSelectionModel.Rows)
        self.headerModel.dataChanged.emit(QModelIndex(), QModelIndex())

        # Load any reduced (processed) data
        reduced = False
        for descriptor in header.descriptordocs:
            if descriptor['name'] == 'reduced':
                reduced = True
                break
        paths = header.startdoc.get('paths')
        for path in paths:
            if reduced:
                startItem = QStandardItem(header.startdoc.get('sample_name', '??'))
                eventlist = header.eventdocs
                for event in eventlist:
                    eventItem = QStandardItem(event['data']['name'])
                    eventItem.setData(event, Qt.UserRole)
                    eventItem.setCheckable(True)
                    startItem.appendRow(eventItem)
                # TODO -- properly add to view (one-time or 2-time, etc.)
                self.oneTimeView.model.invisibleRootItem().appendRow(startItem)

    def getAI(self):
        return None

    def currentheader(self):
        return self.headerModel.itemFromIndex(self.selectionModel.currentIndex()).header

    def currentheaders(self):
        selected_indices = self.selectionModel.selectedIndexes()
        headers = []
        for model_index in selected_indices:
            headers.append(self.headerModel.itemFromIndex(model_index).header)
        return headers

    def processOneTime(self):
        self.process(self.oneTimeProcessor,
                     callback_slot=partial(self.saveResult, fileSelectionView=self.oneTimeFileSelection),
                     finished_slot=partial(self.createDocument, view=self.oneTimeView))

    def processTwoTime(self):
        self.process(self.twoTimeProcessor,
                     callback_slot=partial(self.saveResult, fileSelectionView=self.twoTimeFileSelection),
                     finished_slot=partial(self.createDocument, view=self.twoTimeView))

    def process(self, processor: XPCSProcessor, **kwargs):
        if processor:
            workflow = processor.workflow

            data = [header.meta_array() for header in self.currentheaders()]
            currentWidget = self.rawTabView.currentWidget()
            rois = [item for item in currentWidget.view.items if isinstance(item, BetterROI)]
            labels = [currentWidget.poly_mask()] * len(data)
            numLevels = [1] * len(data)

            numBufs = []
            for i, _ in enumerate(data):
                shape = data[i].shape[0]
                # multi_tau_corr requires num_bufs to be even
                if shape % 2:
                    shape += 1
                numBufs.append(shape)

            if kwargs.get('callback_slot'):
                callbackSlot = kwargs['callback_slot']
            else:
                callbackSlot = self.saveResult
            if kwargs.get('finished_slot'):
                finishedSlot = kwargs['finished_slot']
            else:
                finishedSlot = self.createDocument

            workflowPickle = pickle.dumps(workflow)
            workflow.execute_all(None,
                                 data=data,
                                 labels=labels,
                                 num_levels=numLevels,
                                 num_bufs=numBufs,
                                 callback_slot=callbackSlot,
                                 finished_slot=partial(finishedSlot,
                                                       header=self.currentheader(),
                                                       roi=repr(rois[0]),
                                                       workflow=workflowPickle))
            # TODO -- should header be passed to callback_slot
            # (callback slot handle can handle multiple data items in data list)

    def saveResult(self, result, fileSelectionView=None):
        if fileSelectionView:
            data = dict()
            if not fileSelectionView.correlationName.displayText():
                data['name'] = fileSelectionView.correlationName.placeholderText()
            else:
                data['name'] = fileSelectionView.correlationName.displayText()
            data['result'] = result

            self._results.append(data)

    def createDocument(self, view: CorrelationView, header, roi, workflow):
        self.catalog.upsert(self._createDocument, (self._results, header, roi, workflow), {})
        # TODO -- make sure that this works for multiple selected series to process
        key = list(self.catalog)[-1]

        parentItem = QStandardItem(self._results[-1]['name'])
        for name, doc in self.catalog[key].read_canonical():
            if name == 'event':
                resultsModel = view.model
                # item = QStandardItem(doc['data']['name'])  # TODO -- make sure passed data['name'] is unique in model -> CHECK HERE
                item = QStandardItem(doc['data']['name'])
                item.setData(doc, Qt.UserRole)
                item.setCheckable(True)
                parentItem.appendRow(item)
                selectionModel = view.selectionModel
                selectionModel.reset()
                selectionModel.setCurrentIndex(
                    resultsModel.index(resultsModel.rowCount() - 1, 0), QItemSelectionModel.Rows)
                selectionModel.select(selectionModel.currentIndex(), QItemSelectionModel.SelectCurrent)
        resultsModel.appendRow(parentItem)
        self._results = []

    def _createDocument(self, results, header, roi, workflow):
        timestamp = time.time()

        run_bundle = event_model.compose_run()
        yield 'start', run_bundle.start_doc

        # TODO -- make sure workflow pickles, or try dill / cloudpickle
        source = 'Xi-cam'

        peek_result = results[0]['result']
        g2_shape = peek_result['g2'].value.shape[0]
        # TODO -- make sure g2_err is calculated and added to internal process documents
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
            'fit_curve': {'source': source, 'dtype': 'number', 'shape': [lag_steps_shape]},
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
                      'fit_curve': result['result']['fit_curve'].value,
                      'name': roi,  # TODO update to roi
                      'workflow': workflow},
                timestamps={'g2': timestamp,
                            'g2_err': timestamp,
                            'lag_steps': timestamp,
                            'fit_curve': timestamp,
                            'name': timestamp,
                            'workflow': workflow}
            )

        yield 'stop', run_bundle.compose_stop()
