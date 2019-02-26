from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy import uic
import pyqtgraph as pg

from xicam.core import msg
from xicam.plugins import GUIPlugin, GUILayout, ProcessingPlugin
from xicam.plugins import manager as pluginmanager
from xicam.core.execution import Workflow
from xicam.gui.widgets.tabview import TabView
from xicam.SAXS.widgets.SAXSViewerPlugin import SAXSViewerPlugin
from xicam.core.data import NonDBHeader
from xicam.gui.widgets.imageviewmixins import PolygonROI
from pyqtgraph.parametertree import ParameterTree, Parameter


class TwoTimeProcess(ProcessingPlugin):
    ...


class XPCSWorkflow(Workflow):
    ...


class OneTime(XPCSWorkflow):
    ...


class TwoTime(XPCSWorkflow):
    ...


class XPCSViewerPlugin(PolygonROI, SAXSViewerPlugin):
    pass


class XPCSProcessor(ParameterTree):
    def __init__(self, *args, **kwargs):
        super(XPCSProcessor, self).__init__()

        self.param = Parameter(children=[{'name': 'Algorithm',
                                          'type': 'list',
                                          'values': {'1-time correlation': OneTime,
                                                     '2-time correlation': TwoTime},
                                          'value': '2-time correlation'}])


class XPCS(GUIPlugin):
    name = 'XPCS'

    def __init__(self):
        # Data model
        self.headermodel = QStandardItemModel()
        self.selectionmodel = QItemSelectionModel(self.headermodel)

        # Widgets
        self.calibrationsettings = pluginmanager.getPluginByName('DeviceProfiles', 'SettingsPlugin').plugin_object

        # Toolbar
        self.toolbar = QToolBar()

        # Setup TabViews
        self.rawtabview = TabView(self.headermodel,
                                  widgetcls=XPCSViewerPlugin,
                                  field='ALS:701:_image1_array_data',
                                  selectionmodel=self.selectionmodel,
                                  bindings=[(self.calibrationsettings.sigGeometryChanged, 'setGeometry')],
                                  geometry=self.getAI)

        self.stages = {'XPCS': GUILayout(self.rawtabview,
                                         right=self.calibrationsettings.widget,
                                         top=self.toolbar)}

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
