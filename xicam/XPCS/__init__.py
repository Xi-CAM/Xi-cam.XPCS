from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy import uic
import pyqtgraph as pg

from matplotlib import pyplot as plt

from xicam.core import msg
from xicam.plugins import GUIPlugin, GUILayout, ProcessingPlugin
from xicam.plugins import manager as pluginmanager

from xicam.gui.widgets.tabview import TabView
from xicam.SAXS.widgets.SAXSViewerPlugin import SAXSViewerPluginBase
from xicam.core.data import NonDBHeader
from xicam.gui.widgets.imageviewmixins import PolygonROI
from pyqtgraph.parametertree import ParameterTree, Parameter
from pyqtgraph.parametertree.parameterTypes import ListParameter
from .workflows import OneTime, TwoTime, FourierAutocorrelator
from .widgets.views import CorrelationView, FileSelectionView, OneTimeView, TwoTimeView

import time

import numpy as np # TODO -- this is for debugging
import event_model
from intake_bluesky.in_memory import BlueskyInMemoryCatalog
from functools import partial


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

        # TODO Move catalog outside of this method
        self.catalog = BlueskyInMemoryCatalog()

        self.resultsmodel = QStandardItemModel()

        # Data model
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

        # TODO -- should CorrelationDocument be a member?
        self.correlationdocument = None

        self.__results = []

        super(XPCS, self).__init__()

    def appendHeader(self, header: NonDBHeader, **kwargs):
        item = QStandardItem(header.startdoc.get('sample_name', '????'))
        item.header = header
        self.headermodel.appendRow(item)
        self.selectionmodel.reset()
        self.selectionmodel.setCurrentIndex(self.headermodel.index(self.headermodel.rowCount() - 1, 0),
                                            QItemSelectionModel.Rows)
        self.headermodel.dataChanged.emit(QModelIndex(), QModelIndex())

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

    def process(self, processor: XPCSProcessor, **kwargs):
        # This should always pass, since this is the action for a process toolbar QAction
        if processor:
            # print(self.sender())
            workflow = processor.workflow

            data = [header.meta_array() for header in self.currentheaders()]
            labels = [self.rawtabview.currentWidget().poly_mask()] * len(data)
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

            workflow.execute_all(None,
                                 data=data,
                                 labels=labels,
                                 num_levels=num_levels,
                                 num_bufs=num_bufs,
                                 callback_slot=callback_slot,
                                 finished_slot=finished_slot)

    def processOneTime(self):
        self.process(self.onetimeprocessor,
                     callback_slot=partial(self.saveResult, fileSelectionView=self.onetimefileselection),
                     finished_slot=partial(self.createDocument, view=self.onetimeview))

    def processTwoTime(self):
        self.process(self.twotimeprocessor,
                     callback_slot=partial(self.saveResult, fileSelectionView=self.twotimefileselection),
                     finished_slot=partial(self.createDocument, view=self.twotimeview))

    def saveResult(self, result, fileSelectionView=None):
        # print(result)
        # print(result['g2'].value)
        if fileSelectionView:
            data = dict()
            if not fileSelectionView.correlationname.displayText():
                data['name'] = fileSelectionView.correlationname.placeholderText()
            else:
                data['name'] = fileSelectionView.correlationname.displayText()
            data['result'] = result

            # print(data['name'])
            self.__results.append(data)

    def createDocument(self, view: CorrelationView=None):
        # self.correlationdocument.createEvent(name=data['name'], image_series=data['name'],
        #                                      g2=data['result']['g2'].value)
        self.catalog.upsert(self._createDocument, (self.__results,), {})
        key = list(self.catalog)[-1]

        for name, doc in self.catalog[key].read_canonical():
            if name == 'event':
                resultsmodel = view.model
                item = QStandardItem(doc['data']['name'])  # TODO -- make sure passed data['name'] is unique in model -> CHECK HERE
                item.setData(doc, Qt.UserRole)
                resultsmodel.appendRow(item)
                selectionModel = view.selectionmodel
                selectionModel.reset()
                selectionModel.setCurrentIndex(
                    resultsmodel.index(resultsmodel.rowCount() - 1, 0), QItemSelectionModel.Rows)
                selectionModel.select(selectionModel.currentIndex(), QItemSelectionModel.SelectCurrent)
                # self.currentSelectionModel().selectionChanged.emit(self.currentSelectionModel().selection(), deselected)
                # resultsmodel.dataChanged.emit(resultsmodel.currentIndex())

        self.__results = []
        print()
        print()

    def _createDocument(self, results):
        timestamp = time.time()

        run_bundle = event_model.compose_run()
        yield 'start', run_bundle.start_doc

        data_keys = {'image_series': {'source': 'Xi-cam', 'dtype': 'string', 'shape': []},
                     'g2': {'source': 'Xi-cam XPCS', 'dtype': 'number', 'shape': []},
                     'lag_steps': {'source': 'Xi-cam XPCS', 'dtype': 'number', 'shape': []},
                     'name': {'source': 'Xi-cam', 'dtype': 'string', 'shape': []}
                     }
        stream_bundle = run_bundle.compose_descriptor(data_keys=data_keys, name='primary')
        yield 'descriptor', stream_bundle.descriptor_doc

        for result in results:
            yield 'event', stream_bundle.compose_event(data={'image_series': result['name'],
                                                             'g2': result['result']['g2'].value,
                                                             'lag_steps': result['result']['lag_steps'].value,
                                                             'name': result['name']},
                                                       timestamps={'image_series': timestamp,
                                                                   'g2': timestamp,
                                                                   'lag_steps': timestamp,
                                                                   'name': timestamp})

        yield 'stop', run_bundle.compose_stop()
