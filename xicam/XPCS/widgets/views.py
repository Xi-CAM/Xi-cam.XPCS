from qtpy.QtCore import QItemSelection, Qt
from qtpy.QtGui import QStandardItemModel
from qtpy.QtWidgets import QAbstractItemView, QDialog, QLineEdit, QListView, QVBoxLayout, QWidget

import pyqtgraph as pg


class CorrelationView(QWidget):
    """
    Widget for viewing the correlation results.

    This could be generalized into a ComboPlotView / PlotView / ComboView ...
    """
    def __init__(self, model):
        super(CorrelationView, self).__init__()
        self.model = model  # type: QStandardItemModel
        self.resultslist = QListView(self)
        self.resultslist.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.plot = pg.PlotWidget()
        self.resultslist.setModel(self.model)
        self.selectionmodel = self.resultslist.selectionModel()

        layout = QVBoxLayout()
        layout.addWidget(self.resultslist)
        layout.addWidget(self.plot)
        self.setLayout(layout)

        # Update plot figure whenever selected result changes
        self.selectionmodel.selectionChanged.connect(self.updatePlot)

    def results(self, selection: QItemSelection, dataKey):
        results = []
        for index in selection.indexes():
            eventlist = self.model.data(index, Qt.UserRole)
            # If processing, eventlist contains a dict: {'data': {'g2': [g2curve, g2curve...]}}
            # If loading, eventlist contains a list: [{'data': {'g2': g2curve}}, {'data'...}]
            for i, event in enumerate(eventlist):
                print(f'i, event: {i, event}')
                print(f'type(event["data"][{dataKey}]): {type(event["data"][dataKey])}')
                results.append(event['data'][dataKey])
        return results
        # for index in selection.indexes():
        #     resultData = self.model.data(index, Qt.UserRole)
        #     for result in resultData:
        #         results.append(result['data'][dataKey])
        # return results


    def updatePlot(self, selected, deselected):
        # the selected arg only contains the new selection (not current selection + new selection)
        # TODO -- check multiple items being processed
        self.plot.clear()
        g2 = self.results(self.selectionmodel.selection(), 'g2')
        lag_steps = self.results(self.selectionmodel.selection(), 'lag_steps')
        for step, result in enumerate(g2):
            yData = result.squeeze()
            # Offset x axis by 1 to avoid log10(0) runtime warning at PlotDataItem.py:531
            # xData = np.arange(1, len(yData) + 1)
            xData = lag_steps[step].squeeze()
            self.plot.plot(x=xData, y=yData)
        # self.resultslist.setCurrentIndex(selected.indexes()[-1])

    def createFigure(self):
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
