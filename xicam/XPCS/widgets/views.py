from qtpy.QtCore import Qt, QItemSelection, QPersistentModelIndex
from qtpy.QtGui import QStandardItemModel, QStandardItem
from qtpy.QtWidgets import QAbstractItemView, QDialog, QLineEdit, QListView, QTreeView, QVBoxLayout, QWidget

import pyqtgraph as pg
import numpy as np

# class ResultsView(QTreeView):
#
#     def __init__(self, parent=None):
#         super(ResultsView, self).__init__(parent)

# TODO
# - update 'random' color scheme
# - nice to have add abilities:
#   - to show symbols
#   - to show lines
# - add legend (for curves)
# - get calculated q
# - might be nice to have selection model check/uncheck items
#   - e.g. if selectedItem(s) is checkable: toggle check
#   - model item clicked
# - should the view be editable?
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

        self.resultslist.setSelectionMode(QAbstractItemView.NoSelection)
        self.plotOpts = dict()
        self._plot = pg.PlotWidget(**self.plotOpts)
        self._legend = pg.LegendItem(offset=[-1, 1])
        self.legend.setParentItem(self._plot.getPlotItem())
        self.resultslist.setModel(self.model)
        self.selectionmodel = self.resultslist.selectionModel()

        layout = QVBoxLayout()
        layout.addWidget(self.resultslist)
        layout.addWidget(self._plot)
        self.setLayout(layout)

        self.checkedItemIndexes = []
        self._curves = []
        self.model.itemChanged.connect(self.updatePlot)

    @property
    def plot(self):
        return self._plot

    @property
    def legend(self):
        return self._legend

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

        g2 = list(self.results('g2'))
        g2_err = list(self.results('g2_err'))
        lag_steps = list(self.results('lag_steps'))
        roi_list = list(self.results('name'))
        self.plot.clear()
        for curve in self._curves:
            self.legend.removeItem(curve)
        self._curves.clear()
        for roi in range(len(self.checkedItemIndexes)):
            yData = g2[roi].squeeze()
            # Offset x axis by 1 to avoid log10(0) runtime warning at PlotDataItem.py:531
            xData = lag_steps[roi].squeeze()
            color = [float(roi) / len(self.checkedItemIndexes) * 255,
                     (1 - float(roi) / len(self.checkedItemIndexes)) * 255,
                     255]
            self.plotOpts['pen'] = color
            err = g2_err[roi].squeeze()
            self.plot.addItem(pg.ErrorBarItem(x=np.log10(xData), y=yData, top=err, bottom=err, **self.plotOpts))
            curve = self.plot.plot(x=xData, y=yData, **self.plotOpts)
            self._curves.append(curve)

            self.legend.addItem(curve, name=repr(roi_list[roi]))


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
