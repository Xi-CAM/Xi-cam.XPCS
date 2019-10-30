import pathlib
import time
from functools import partial

import cloudpickle as pickle
import event_model
from databroker.core import BlueskyRun
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

from .widgets.views import CorrelationWidget, FileSelectionView, OneTimeWidget, TwoTimeWidget
from .workflows import FourierAutocorrelator, OneTime, TwoTime


class BlueskyItem(QStandardItem):

    def __init__(self):
        super(QStandardItem, self).__init__()


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
        self.twoTimeView = TwoTimeWidget()
        self.twoTimeFileSelection = FileSelectionView(self.headerModel, self.selectionModel)
        self.twoTimeProcessor = TwoTimeProcessor()
        self.twoTimeToolBar = QToolBar()
        self.twoTimeToolBar.addAction(QIcon(static.path('icons/run.png')), 'Process', self.processTwoTime)
        self.twoTimeToolBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.oneTimeView = OneTimeWidget()
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
            if descriptor['name'] == '1-Time':
                reduced = True
                break
        paths = header.startdoc.get('paths')
        for path in paths:
            if reduced:
                startItem = QStandardItem(header.startdoc.get('sample_name', '??'))
                eventlist = header.eventdocs
                for event in eventlist:
                    eventItem = QStandardItem(repr(event['data']['dqlist']))
                    eventItem.setData(event, Qt.UserRole)
                    eventItem.setCheckable(True)
                    startItem.appendRow(eventItem)
                # TODO -- properly add to view (one-time or 2-time, etc.)
                self.oneTimeView.model.invisibleRootItem().appendRow(startItem)

    def appendCatalog(self, catalog: BlueskyRun, **kwargs):
        displayName = ""
        if 'sample_name' in catalog.metadata['start']:
            displayName = catalog.metadata['start']['sample_name']
        elif 'scan_id' in catalog.metadata['start']:
            displayName = catalog.metadata['start']['scan_id']
        else:
            displayName = catalog.metadata['start']['uid']

        item = BlueskyItem(displayName)
        item.setData(catalog, Qt.UserRole)
        self.catalogModel.appendRow(item)
        self.catalogModel.dataChanged.emit(item.index(), item.index())

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
        canvas = self.oneTimeView.plot
        canvases = dict()  # Intentionally empty; unused in PlotHint
        self.process(self.oneTimeProcessor,
                     callback_slot=partial(self.saveResult, fileSelectionView=self.oneTimeFileSelection),
                     finished_slot=partial(self.updateDerivedDataModel,
                                           view=self.oneTimeView,
                                           canvas=canvas,
                                           canvases=canvases))

    def processTwoTime(self):
        canvas = None  # Intentionally empty; unused in ImageHint
        canvases = {"imageview": self.twoTimeView.image}
        self.process(self.twoTimeProcessor,
                     callback_slot=partial(self.saveResult, fileSelectionView=self.twoTimeFileSelection),
                     finished_slot=partial(self.updateDerivedDataModel,
                                           view=self.twoTimeView,
                                           canvas=canvas,
                                           canvases=canvases))

    def process(self, processor: XPCSProcessor, **kwargs):
        if processor:
            workflow = processor.workflow

            data = [header.meta_array() for header in self.currentheaders()]
            currentWidget = self.rawTabView.currentWidget()
            rois = [item for item in currentWidget.view.items if isinstance(item, BetterROI)]
            labels = [currentWidget.poly_mask()] * len(data)  # TODO: update for multiple ROIs
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
                finishedSlot = self.updateDerivedDataModel

            workflowPickle = pickle.dumps(workflow)
            workflow.execute_all(None,
                                 data=data,
                                 labels=labels,
                                 num_levels=numLevels,
                                 num_bufs=numBufs,
                                 callback_slot=callbackSlot,
                                 finished_slot=partial(finishedSlot,
                                                       header=self.currentheader(),
                                                       roi=rois[0],  # todo -- handle multiple rois
                                                       workflow=workflow,
                                                       workflow_pickle=workflowPickle))

    def saveResult(self, result, fileSelectionView=None):
        if fileSelectionView:
            analyzed_results = dict()

            if not fileSelectionView.correlationName.displayText():
                analyzed_results['result_name'] = fileSelectionView.correlationName.placeholderText()
            else:
                analyzed_results['result_name'] = fileSelectionView.correlationName.displayText()
            analyzed_results = {**analyzed_results, **result}

            self._results.append(analyzed_results)

    def updateDerivedDataModel(self, view: CorrelationWidget, canvas, canvases, header, roi, workflow, workflow_pickle):
        parentItem = BlueskyItem(workflow.name)
        for hint in workflow.hints:
            item = BlueskyItem(hint.name)
            item.setData(hint)
            item.setCheckable(True)
            parentItem.appendRow(item)
