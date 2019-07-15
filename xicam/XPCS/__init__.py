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
from .workflows import OneTime, TwoTime, FourierAutocorrelator
from .widgets.onetimeplot import OneTimePlotWidget

# from . import CorrelationPlugin
import time

# class TwoTimeProcess(ProcessingPlugin):
#     ...
#
#

import numpy as np # TODO -- this is for debugging
from .CorrelationDocument import CorrelationDocument
import event_model
from intake_bluesky.in_memory import BlueskyInMemoryCatalog
from functools import partial


class XPCSViewerPlugin(PolygonROI, SAXSViewerPluginBase):
    pass


class XPCSProcessor(ParameterTree):
    def __init__(self, *args, **kwargs):
        super(XPCSProcessor, self).__init__()
        self._name = 'Algorithm'
        self._type = 'list'
        self._values = {}
        self._value = ''


class OneTimeProcessor(XPCSProcessor):
    def __init__(self, *args, **kwargs):
        super(OneTimeProcessor, self).__init__()
        for k, v in OneTimeAlgorithms.categories().items():
            self._values[k] = v
        self._value = OneTimeAlgorithms.default()

        children = [{'name': self._name,
                         'type': 'list',
                         'values': self._values,
                         'value': self._value}]
        children += OneTime().parameters # TODO
        self.param = Parameter(children=children, name='1-Time Processor')
        self.setParameters(self.param, showTop=False)


class TwoTimeProcessor(XPCSProcessor):
    def __init__(self, *args, **kwargs):
        super(TwoTimeProcessor, self).__init__()
        for k, v in TwoTimeAlgorithms.categories().items():
            self._values[k] = v
        self._value = TwoTimeAlgorithms.default()
        self.param = Parameter(children=[{'name': self._name,
                                          'type': self._type,
                                          'values': self._values,
                                          'value': self._value}], name='2-Time Processor')
        self.setParameters(self.param, showTop=False)


class ProcessingCategories:
    @staticmethod
    def categories():
        return {
            TwoTimeAlgorithms.name: TwoTimeAlgorithms.categories(),
            OneTimeAlgorithms.name: OneTimeAlgorithms.categories()
        }


class TwoTimeAlgorithms(ProcessingCategories):
    name = '2-Time Algorithms'
    @staticmethod
    def categories():
        return {TwoTime.name: TwoTime}

    @staticmethod
    def default():
        return TwoTime.name


class OneTimeAlgorithms(ProcessingCategories):
    name = '1-Time Algorithms'
    @staticmethod
    def categories():
        return {OneTime.name: OneTime,
                FourierAutocorrelator.name: FourierAutocorrelator}

    @staticmethod
    def default():
        return OneTime.name


class CorrelationView(QWidget):
    """
    Widget for viewing the correlation results.

    This could be generalized into a ComboPlotView / PlotView / ComboView ...
    """
    def __init__(self, model):
        super(CorrelationView, self).__init__()
        self.resultslist = QComboBox()

        self.plot = pg.PlotWidget()

        self.model = model # type: QStandardItemModel
        self.resultslist.setModel(self.model)
        self.selectionmodel = self.resultslist.view().selectionModel()

        layout = QVBoxLayout()
        layout.addWidget(self.resultslist)
        layout.addWidget(self.plot)
        self.setLayout(layout)

        # Update plot figure whenever selected result changes
        self.selectionmodel.selectionChanged.connect(self.updatePlot)

    def results(self, selection: QItemSelection, dataKey):
        results = []
        for index in selection.indexes():
            # for result in self.model.itemFromIndex(index).header['data'][dataKey]:
            #     results.append(result)
            results.append(self.model.data(index, Qt.UserRole)['data'][dataKey].value)
            # results.append(self.model.itemFromIndex(index).data(DOC_ROLE)['data'][dataKey].value)
        return results

    def updatePlot(self, selected, deselected):
        # TODO -- when multiple items selected to process, 2 items are added to the plot combo box (2 plot
        # items exist in the plot widget, which is good though)
        self.plot.clear()
        for result in self.results(selected, 'g2'):
            yData = result.squeeze()
            # Offset x axis by 1 to avoid log10(0) runtime error at PlotDataItem.py:531
            xData = np.arange(1, len(yData) + 1)
            self.plot.plot(x=xData, y=yData)
        self.resultslist.setCurrentIndex(0)#selected.indexes()[:-1].row())


class OneTimeView(CorrelationView):
    def __init__(self):
        self.model = QStandardItemModel()
        super(OneTimeView, self).__init__(self.model)
        plotItem = self.plot.getPlotItem()
        plotItem.setLabel('left', 'g<sub>2</sub>(&tau;)', 's')
        plotItem.setLabel('bottom', '&tau;', 's')
        plotItem.setLogMode(x=True)


class TwoTimeView(CorrelationView):
    def __init__(self):
        self.model = QStandardItemModel()
        super(TwoTimeView, self).__init__(self.model)
        plotItem = self.plot.getPlotItem()
        plotItem.setLabel('left', 't<sub>2</sub>', 's')
        plotItem.setLabel('bottom', 't<sub>1</sub>', 's')


class FileSelectionView(QWidget):
    """
    Widget for viewing and selecting the loaded files.
    """
    def __init__(self, headermodel, selectionmodel):
        """

        Parameters
        ----------
        headermodel
            The model to use in the file list view
        selectionmodel
            The selection model to use in the file list view
        """
        super(FileSelectionView, self).__init__()
        # self.parameters = ParameterTree()
        self.filelistview = QListView()
        self.correlationname = QLineEdit()
        self.correlationname.setPlaceholderText('Name of result')

        layout = QVBoxLayout()
        layout.addWidget(self.filelistview)
        layout.addWidget(self.correlationname)
        self.setLayout(layout)

        self.headermodel = headermodel
        self.selectionmodel = selectionmodel
        self.filelistview.setModel(headermodel)
        self.filelistview.setSelectionModel(selectionmodel)
        self.filelistview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.filelistview.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Make sure when the tabview selection model changes, the file list
        # current item updates
        self.selectionmodel.currentChanged.connect(
            lambda current, _:
                self.filelistview.setCurrentIndex(current)
        )

        self.selectionmodel.currentChanged.connect(
            lambda current, _:
                self.correlationname.setPlaceholderText(current.data())
        )


class XPCS(GUIPlugin):
    name = 'XPCS'

    def __init__(self):

        self.resultsmodel = QStandardItemModel()

        # Data model
        self.headermodel = QStandardItemModel()
        self.selectionmodel = QItemSelectionModel(self.headermodel)

        # Widgets
        self.calibrationsettings = pluginmanager.getPluginByName('xicam.SAXS.calibration',
                                                                 'SettingsPlugin').plugin_object
        self.plotwidget = OneTimePlotWidget()
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
            workflow = processor.param['Algorithm']()

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
        print(result)
        print(result['g2'].value)
        if fileSelectionView:
            data = dict()
            if not fileSelectionView.correlationname.displayText():
                data['name'] = fileSelectionView.correlationname.placeholderText()
            else:
                data['name'] = fileSelectionView.correlationname.displayText()
            data['result'] = result

            print(data['name'])
            self.__results.append(data)

    def createDocument(self, view: CorrelationView=None):
        # self.correlationdocument.createEvent(name=data['name'], image_series=data['name'],
        #                                      g2=data['result']['g2'].value)
        # TODO Move catalog outside of this method
        catalog = BlueskyInMemoryCatalog()
        catalog.upsert(self._createDocument, (self.__results,), {})
        key = list(catalog)[0]

        for name, doc in catalog[key].read_canonical():
            if name == 'event':
                resultsmodel = view.model
                item = QStandardItem(doc['data']['name'])  # TODO -- make sure passed data['name'] is unique in model -> CHECK HERE
                item.setData(doc, Qt.UserRole)
                resultsmodel.appendRow(item)
                selectionModel = view.selectionmodel
                deselected = selectionModel.selection()
                selectionModel.setCurrentIndex(
                    resultsmodel.index(resultsmodel.rowCount() - 1, 0), QItemSelectionModel.Rows)
                selectionModel.select(selectionModel.currentIndex(), QItemSelectionModel.SelectCurrent)
                # self.currentSelectionModel().selectionChanged.emit(self.currentSelectionModel().selection(), deselected)
                resultsmodel.dataChanged.emit(QModelIndex(), QModelIndex())

        self.__results = []
        print()
        print()

    def _createDocument(self, results):
        timestamp = time.time()

        run_bundle = event_model.compose_run()
        yield 'start', run_bundle.start_doc

        data_keys = {'image_series': {'source': 'Xi-cam', 'dtype': 'string', 'shape': []},
                     'g2': {'source': 'Xi-cam XPCS', 'dtype': 'number', 'shape': [],},
                     'name': {'source': 'Xi-cam', 'dtype': 'string', 'shape': []}
                     }
        stream_bundle = run_bundle.compose_descriptor(data_keys=data_keys, name='primary')
        yield 'descriptor', stream_bundle.descriptor_doc

        for result in results:
            yield 'event', stream_bundle.compose_event(data={'image_series': result['name'],
                                                             'g2': result['result']['g2'],
                                                             'name': result['name']},
                                                       timestamps={'image_series': timestamp,
                                                                   'g2': timestamp,
                                                                   'name': timestamp})

        yield 'stop', run_bundle.compose_stop()
