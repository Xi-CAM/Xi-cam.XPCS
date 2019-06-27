import pyqtgraph as pg
from qtpy.QtCore import QSize


class OneTimePlotWidget(pg.PlotWidget):
    def sizeHint(self):
        return QSize(150, 200)
