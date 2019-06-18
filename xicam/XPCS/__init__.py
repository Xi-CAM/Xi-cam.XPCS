from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy import uic
import pyqtgraph as pg

from xicam.core import msg
from xicam.plugins import GUIPlugin, GUILayout, ProcessingPlugin
from xicam.plugins import manager as pluginmanager

from xicam.gui.widgets.tabview import TabView
from xicam.SAXS.widgets.SAXSViewerPlugin import SAXSViewerPlugin
from xicam.core.data import NonDBHeader
from xicam.gui.widgets.imageviewmixins import PolygonROI
from pyqtgraph.parametertree import ParameterTree, Parameter
from .workflows import OneTime, TwoTime, FourierAutocorrelator

from . import CorrelationPlugin

# class TwoTimeProcess(ProcessingPlugin):
#     ...
#
#


class XPCSViewerPlugin(PolygonROI, SAXSViewerPlugin):
    pass


class XPCSProcessor(ParameterTree):
    def __init__(self, *args, **kwargs):
        super(XPCSProcessor, self).__init__()

        self.param = Parameter(children=[{'name': 'Algorithm',
                                          'type': 'list',
                                          'values': {OneTime.name: OneTime,
                                                     TwoTime.name: TwoTime,
                                                     FourierAutocorrelator.name: FourierAutocorrelator},
                                          'value': FourierAutocorrelator.name}], name='Processor')
        self.setParameters(self.param, showTop=False)


#TODO move this class
class CorrelationView(QWidget):
    def __init__(self):
        super(CorrelationView, self).__init__()
        self.resultslist = QComboBox()
        self.plot = QWidget()

        self.headermodel = QStandardItemModel()
        self.selectionmodel = QItemSelectionModel(self.headermodel)

        layout = QVBoxLayout()
        layout.addWidget(self.resultslist)
        layout.addWidget(self.plot)
        self.setLayout(layout)


class CorrelationParameters(QWidget):
    def __init__(self):
        super(CorrelationParameters, self).__init__()
        self.parameters = ParameterTree()
        self.listview = QListView()
        self.runbutton = QPushButton(text='Correlate')

        layout = QVBoxLayout()
        layout.addWidget(self.parameters)
        layout.addWidget(self.listview)
        layout.addWidget(self.runbutton)
        self.setLayout(layout)


class XPCS(GUIPlugin):
    name = 'XPCS'

    def __init__(self):
        # Data model
        self.headermodel = QStandardItemModel()
        self.selectionmodel = QItemSelectionModel(self.headermodel)

        # Widgets
        self.calibrationsettings = pluginmanager.getPluginByName('xicam.SAXS.calibration',
                                                                 'SettingsPlugin').plugin_object
        self.plotwidget = pg.PlotWidget()
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

        # Setup correlation view
        self.correlationview = CorrelationView()
        self.correlationsettings = QLabel('test')
        self.correlationparameters = CorrelationParameters()

        self.stages = {'Raw(change)': GUILayout(self.rawtabview,
                                         right=self.calibrationsettings.widget,
                                         top=self.toolbar,
                                         rightbottom=self.processor),
                       'Correlate': GUILayout(self.correlationview,
                                              top=self.toolbar,
                                              right=self.correlationparameters,
                                              bottom=self.correlationsettings)
                       }

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

    def process(self):
        workflow = self.processor.param['Algorithm']()
        workflow.execute(data=self.currentheader().meta_array(),
                         labels=self.rawtabview.currentWidget().poly_mask(),
                         callback_slot=self.show_g2)

    def show_g2(self, result):
        self.plotwidget.clear()
        self.plotwidget.plot(result['g2'].value.squeeze())
