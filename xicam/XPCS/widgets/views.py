from qtpy.QtCore import Qt, QItemSelection, QPersistentModelIndex
from qtpy.QtGui import QStandardItemModel, QStandardItem
from qtpy.QtWidgets import QAbstractItemView, QDialog, QLineEdit, QListView, QTreeView, QVBoxLayout, QWidget

import pyqtgraph as pg


# class ResultsView(QTreeView):
#
#     def __init__(self, parent=None):
#         super(ResultsView, self).__init__(parent)


class CorrelationView(QWidget):
    """
    Widget for viewing the correlation results.

    This could be generalized into a ComboPlotView / PlotView / ComboView ...
    """
    def __init__(self, model):
        super(CorrelationView, self).__init__()
        self.model = model  # type: QStandardItemModel
        self.resultslist = QTreeView(self)
        self.resultslist.setHeaderHidden(True)

        # from qtpy.QtGui import QStandardItem
        # m = QStandardItemModel()
        # root = m.invisibleRootItem()
        # m.appendRow(QStandardItem('aaa'))
        # parentItem = QStandardItem('bbb')
        # m.appendRow(parentItem)
        # parentItem.appendRow(QStandardItem('bbb child'))
        # self.resultslist.setModel(m)
        # self.resultslist.setSelectionMode(QAbstractItemView.NoSelection)

        # self.resultslist.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.resultslist.setSelectionMode(QAbstractItemView.NoSelection)
        self.plotOpts = {
            'antialias': True,
            'pen': 'r'
        }
        self._plot = pg.PlotWidget(**self.plotOpts)
        self.resultslist.setModel(self.model)
        self.selectionmodel = self.resultslist.selectionModel()

        layout = QVBoxLayout()
        layout.addWidget(self.resultslist)
        layout.addWidget(self._plot)
        self.setLayout(layout)

        # Update plot figure whenever selected result changes
        # self.selectionmodel.selectionChanged.connect(self.updatePlot)

        self.checkedItemIndexes = []
        self.model.itemChanged.connect(self.updatePlot)

    @property
    def plot(self):
        return self._plot

    def results(self, dataKey):
        for index in self.checkedItemIndexes:
            yield index.data(Qt.UserRole)['data'][dataKey]

    def updatePlot(self, item: QStandardItem):
        itemIndex = QPersistentModelIndex(item.index())
        if item.checkState():
            self.checkedItemIndexes.append(itemIndex)
        else:
            # TODO -- might need try for ValueError
            self.checkedItemIndexes.remove(itemIndex)

        self.plot.clear()
        g2 = list(self.results('g2'))
        lag_steps = list(self.results('lag_steps'))
        # for step, result in enumerate(g2):
        numCheckedRois = len(g2)
        # TODO -- temp, need to actually get number of selected ROIs
        # if numCheckedRois > 3:
        #     numCheckedRois = 3
        for roi in range(numCheckedRois):
            yData = g2[roi].squeeze()
            # Offset x axis by 1 to avoid log10(0) runtime warning at PlotDataItem.py:531
            xData = lag_steps[roi].squeeze()
            self.plotOpts['pen'] = (roi, numCheckedRois)
            self.plot.plot(x=xData, y=yData, **self.plotOpts, )
        # itemKey = item.parent().data(Qt.DisplayRole) + item.data(Qt.DisplayRole)
        # if item.checkState():
        #     self.checkedItems[itemKey] = item
        # else:
        #     if self.checkedItems.get(itemKey):
        #         self.checkedItems.pop(itemKey)
        #
        # self.plot.clear()
        # for item in self.checkedItems.values():
        #     eventDoc = item.data(Qt.UserRole)
        #     for i, event in enumerate(eventDoc):


    # def results(self, selection: QItemSelection, dataKey):
    #     results = []
    #     # TODO -- handle when parent item is selected
    #     for index in selection.indexes():
    #         results.append(self.model.data(index, Qt.UserRole)['data'][dataKey])
    #     # for index in selection.indexes():
    #     #     eventlist = self.model.data(index, Qt.UserRole)
    #     #     for i, event in enumerate(eventlist):
    #     #         results.append(event['data'][dataKey])
    #     return results
    #
    # def updatePlot(self, selected, deselected):
    #     # the selected arg only contains the new selection (not current selection + new selection)
    #     # TODO -- check multiple items being processed
    #     self.plot.clear()
    #     g2 = self.results(self.selectionmodel.selection(), 'g2')
    #     lag_steps = self.results(self.selectionmodel.selection(), 'lag_steps')
    #     # for step, result in enumerate(g2):
    #     numSelectedRois = len(g2)
    #     # TODO -- temp, need to actually get number of selected ROIs
    #     # if numSelectedRois > 3:
    #     #     numSelectedRois = 3
    #     for roi in range(numSelectedRois):
    #         yData = g2[roi].squeeze()
    #         # Offset x axis by 1 to avoid log10(0) runtime warning at PlotDataItem.py:531
    #         xData = lag_steps[roi].squeeze()
    #         self.plot.plot(x=xData, y=yData)

    def createFigure(self):
        # TODO -- each event represents an ROI, which represents a grid item
        # TODO -- each file will show a curve in each grid item
        # -- e.g. 3 files, 5 ROIS will show 5 grid items, each with 3 curves
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec

        # TODO -- hook in the qslicing
        qslice = 1

        figure = plt.figure()
        grid_spec = gridspec.GridSpec(3, 3)
        selection = self.selectionmodel.selection()
        legend = []
        for index in selection.indexes():
            legend.append(index.data(Qt.DisplayRole))
        for q in range(qslice):
            ax = figure.add_subplot(grid_spec[q % 3, q // 3], label=q)
            ax.set_xscale('log')
            g2 = self.results(selection, 'g2')
            lag_steps = self.results(selection, 'lag_steps')
            for step, result in enumerate(g2):
                yData = result.squeeze()
                xData = lag_steps[step].squeeze()
                plt.plot(xData, yData, 'D-', fillstyle='none')
            ax.legend(legend)

        plt.show()  # TODO -- "QCoreApplication::exec: The event loop is already running"


class OneTimeView(CorrelationView):
    def __init__(self):
        self.model = QStandardItemModel()
        super(OneTimeView, self).__init__(self.model)
        plotItem = self._plot.getPlotItem()
        plotItem.setLabel('left', 'g<sub>2</sub>(&tau;)', 's')
        plotItem.setLabel('bottom', '&tau;', 's')
        plotItem.setLogMode(x=True)


class TwoTimeView(CorrelationView):
    def __init__(self):
        self.model = QStandardItemModel()
        super(TwoTimeView, self).__init__(self.model)
        plotItem = self._plot.getPlotItem()
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
