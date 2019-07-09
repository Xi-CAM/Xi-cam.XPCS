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

# from . import CorrelationPlugin

# class TwoTimeProcess(ProcessingPlugin):
#     ...
#
#

import numpy as np # TODO -- this is for debugging
from .CorrelationDocument import CorrelationDocument
import event_model

class XPCSViewerPlugin(PolygonROI, SAXSViewerPluginBase):
    pass


class XPCSProcessor(ParameterTree):
    def __init__(self, *args, **kwargs):
        super(XPCSProcessor, self).__init__()
        self._name = 'Algorithm'
        self._type = 'list'
        self._values = {}
        self._value = ''

        # self.param = Parameter(children=[{'name': self._name,
        #                                   'type': self._type,
        #                                   'values': self._values,
        #                                   'value': self._value}], name='Processor')
        #
        # self.setParameters(self.param, showTop=False)


class OneTimeProcessor(XPCSProcessor):
    def __init__(self, *args, **kwargs):
        super(OneTimeProcessor, self).__init__()
        for k, v in OneTimeAlgorithms.categories().items():
            self._values[k] = v
        self._value = OneTimeAlgorithms.default()
        self.param = Parameter(children=[{'name': self._name,
                                          'type': 'list',
                                          'values': self._values,
                                          'value': self._value}], name='1-Time Processor')
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
        # self.selectionmodel.currentChanged.connect(self.updatePlot)
        self.selectionmodel.selectionChanged.connect(self.updatePlot)
    # def results(self, modelIndex, dataKey):
    #     return self.model.itemFromIndex(modelIndex).header.data(dataKey)

    def results(self, selection: QItemSelection, dataKey):
        results = []
        for index in selection.indexes():
            for result in self.model.itemFromIndex(index).header.data(dataKey):
                results.append(result)
        return results

    def updatePlot(self, selected, deselected):
        # TODO -- when multiple items selected to process, 2 items are added to the plot combo box (2 plot
        # items exist in the plot widget, which is good though)
        self.plot.clear()
        for result in self.results(selected, 'g2'):
            self.plot.plot(result.squeeze())
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

        # Toolbar
        # self.toolbar = QToolBar()
        # self.toolbar.addAction('Process', self.process)

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
        self.twotimetoolbar.addAction('Process', self.process)
        self.onetimeview = OneTimeView()
        self.onetimefileselection = FileSelectionView(self.headermodel, self.selectionmodel)
        self.onetimeprocessor = OneTimeProcessor()
        self.onetimetoolbar = QToolBar()
        self.onetimetoolbar.addAction('Process', self.process)

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
        repr(self.correlationdocument)

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

    def addResults(self, data):
        # self.correlationdocument.setShape('g2', data['result']['g2'].value.shape)
        # self.correlationdocument.createDescriptor()
        self.correlationdocument.createEvent(name=data['name'], image_series=data['name'], g2=data['result']['g2'].value)
        item = QStandardItem(data['name']) # TODO -- make sure passed data['name'] is unique in model -> CHECK HERE
        item.header = self.correlationdocument
        resultsmodel = self.currentModel()
        resultsmodel.appendRow(item)
        deselected = self.currentSelectionModel().selection()
        self.currentSelectionModel().setCurrentIndex(
            resultsmodel.index(resultsmodel.rowCount() - 1, 0), QItemSelectionModel.Rows)
        self.currentSelectionModel().selectionChanged.emit(self.currentSelectionModel().selection(), deselected)
        # self.selectionmodel.setCurrentIndex(
        #     self.model.index(self.model.rowCount() - 1, 0), QItemSelectionModel.Rows)
        resultsmodel.dataChanged.emit(QModelIndex(), QModelIndex())
        # self.correlationdocument.createStop()
        print()

    # TODO better way to do this (sig, slot)
    def currentProcessor(self):
        processor = self.stage['rightbottom']
        if isinstance(processor, XPCSProcessor):
            return processor
        else:
            return None

    def currentSelectionModel(self):
        if isinstance(self.stage['center'], CorrelationView):
            return self.stage['center'].selectionmodel
        else:
            return None

    def currentFileSelectionView(self):
        if isinstance(self.stage['right'], FileSelectionView):
            return self.stage['right']
        else:
            return None

    def currentModel(self):
        if isinstance(self.stage['center'], CorrelationView):
            return self.stage['center'].model
        else:
            return None

    # def currentSelectionModel(self):
    #     model = self.currentModel()
    #     if model:
    #         return

    def process(self):
        # This should always pass, since this is the action for a process toolbar QAction
        if self.currentProcessor():
            self.correlationdocument = CorrelationDocument(self.currentheader(), 'x')
            # print(self.sender())
            workflow = self.currentProcessor().param['Algorithm']()

            data = [header.meta_array() for header in self.currentheaders()]
            labels = [self.rawtabview.currentWidget().poly_mask()] * len(data)
            workflow.execute_all(None,
                                 data=data,
                                 labels=labels,
                                 callback_slot=self.show_g2,
                                 #callback_slot=self.show_g2,
                                 finished_slot=self.finished_slot)

            # To use createDocument() function instead of class, use callback_slot to collect the results,
            # then use finished_slot to call createDocument(results) to create a document with multiple events
            # (i.e. multiple items selected)

    def finished_slot(self):
        self.correlationdocument.createStop()
        print()

    def show_g2(self, result):
        print(result)
        print(result['g2'].value)
        data = dict()
        fileselectionview = self.currentFileSelectionView()
        # TODO -- handle unique name - (data['name']) will be same regardless what image(s) are selected
        if not fileselectionview.correlationname.displayText():
            data['name'] = fileselectionview.correlationname.placeholderText()
        else:
            data['name'] = fileselectionview.correlationname.displayText()

        data['result'] = result
        print(data['name'])

        try:
            self.addResults(data)
            # self.correlationdocument.createStop()
            # if only a single image was selected, the value is 0 length.
            # self.correlationview.plotwidget.plot(result['g2'].value.squeeze())

            # Temporary -- just populating the combobox w/out model
            # self.correlationview.resultslist.addItem(
            #     self.currentheader().startdoc['sample_name'])
        except TypeError:
            # occurs when only 1 image is selected and then 'process' is clicked
            # i.e. not a series of images
            # TODO -- how to handle selection of non-series items?
            QMessageBox.warning(QApplication.activeWindow(),
                                'Only one image selected',
                                'Please select more than one image')
        # add event and stop to the correlation document
        # TODO -- do we need the document? Why not just add to a model?
        # self.correlationdocument.add()



