from typing import Callable, Union, Dict, List
from qtpy.QtCore import Qt, QAbstractProxyModel, QIdentityProxyModel, QModelIndex, QItemSelection, QPersistentModelIndex
from xicam.SAXS.data.ensemble import Ensemble, EnsembleModel
from xicam.XPCS.intents import Intent
from xicam.XPCS.intents.canvases import IntentCanvas

# IntentCanvas -> SingleIntentCanvas -> ImageIntentCanvas
#              -> MultipleIntentCanvas -> PlotItentCanvas

# IntentCanvas.serialize() -> raise NIE
# IntentCanvas.deserialize() -> raise NIE
# not implemented for most derived classes


# How do we be friendly to Jupyter land?
# Use a manager object that sits above Xi-cam land and Generic land
# manager object has a standardized interface for dispatching intents to canvases
# Xi-cam: ProxyModel
# JupyterLand: whatever implements that interface

# Intent.canvas should be dict[Environment(QT | Jupyter): canvases]

class CanvasProxyModel(QIdentityProxyModel):
    """Maps data to appropriate render target."""
    def __init__(self, *args, **kwargs):
        super(CanvasProxyModel, self).__init__(*args, **kwargs)
        self._canvas_to_indexes_map = {}   # Dict[HintCanvas, List[QPersistentModelIndex]]

    def canvas_from_index(self, index) -> IntentCanvas:
        canvas = self.data(index, self.CanvasRole)
        if canvas is not None:
            return canvas
        else:
            canvas = self.create_canvas(index)
        return canvas

    @staticmethod
    def create_canvas(index):
        ...

    @staticmethod
    def create_canvas(canvas_type, *canvas_args, **canvas_kwargs):
        if canvas_type:
            canvas = canvas_type(*canvas_args, **canvas_kwargs)
            return canvas

    def add_data_to_canvas(self, canvas: IntentCanvas, data: Intent, index: QPersistentModelIndex):
        if canvas:
            canvas.render(data)
            self._canvas_to_indexes_map[canvas] = index


    # self.data(index, role=UserRole+1 (CanvasRole...)
    def find_canvases(self, search_index):
        canvases = []
        for canvas, indexes in self._canvas_to_indexes_map:
            for index in indexes:
                if index == search_index:
                    canvases += canvas
        return canvases

    def data(self, index, role=Qt.DisplayRole):
        if role != Qt.UserRole:
            return super(CanvasProxyModel, self).data(index, role)

        source_index = self.mapToSource(index)
        data = self.sourceModel().data(source_index, role=role)

        p_index = QPersistentModelIndex(index)
        canvases = self.find_canvases(p_index)
        if canvases:
            canvas = canvases[0]  # TODO don't always grab first canvas
        else:
            canvas_type = getattr(data, "canvas", None)
            canvas = self.create_canvas(canvas_type)
        canvas.render(data)
        # TODO : canvas.render(intent, index)
        # TODO: canvas.unrender(intent, index) needs to be implemented
        return data


class ExampleDerivedIdentityProxyModel(QIdentityProxyModel):
    def __init__(self, *args, **kwargs):
        super(CanvasProxyModel, self).__init__(*args, **kwargs)
        self._modifier_func = str.upper

    def set_modifier_func(self, func: Callable[[str], str]) -> None:
        self._modifier_func(func)

    def data(self, index, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return super(CanvasProxyModel, self).data(index, role)

        source_index = self.mapToSource(index)
        data = self.sourceModel().data(source_index, role=role)
        if data:
            return self._modifier_func(data)
        return None


class ExampleDerivedFromAbstractProxyModel(QAbstractProxyModel):

    def __init__(self, *args, **kwargs):
        super(ExampleDerivedFromAbstractProxyModel, self).__init__(*args, **kwargs)
        self._mapping = {}  # Map from this model (proxy) indexes to source model indexes

    def mapFromSource(self, sourceIndex: QModelIndex) -> QModelIndex:
        if not sourceIndex.isValid():
            return QModelIndex()
        # Look-up by source index by value in the mapping dict
        return next((proxy_index for proxy_index, source_index in self._mapping.items()
                     if source_index == sourceIndex), QModelIndex())

    def mapToSource(self, proxyIndex: QModelIndex) -> QModelIndex:
        if not proxyIndex.isValid():
            return QModelIndex()
        return self._mapping.get(proxyIndex, QModelIndex())

    # def mapSelectionFromSource(self, sourceSelection: QItemSelection) -> QItemSelection:
    #     ...
    #
    # def mapSelectionToSource(self, proxySelection: QItemSelection) -> QItemSelection:
    #     ...


if __name__ == "__main__":
    from databroker.in_memory import BlueskyInMemoryCatalog
    from qtpy.QtWidgets import QApplication, QMainWindow, QSplitter, QListView
    from xicam.SAXS.widgets.views import ResultsTabView, DataSelectorView
    from xicam.XPCS.ingestors import ingest_nxXPCS

    app = QApplication([])


    uris = ["/home/ihumphrey/Downloads/B009_Aerogel_1mm_025C_att1_Lq0_001_0001-10000.nxs"]
    document = list(ingest_nxXPCS(uris))
    uid = document[0][1]["uid"]
    catalog = BlueskyInMemoryCatalog()
    catalog.upsert(document[0][1], document[-1][1], ingest_nxXPCS, [uris], {})
    cat = catalog[uid]

    source_model = EnsembleModel()
    ensemble = Ensemble()
    ensemble.append_catalog(cat)
    source_model.add_ensemble(ensemble)
    # for i in range(3):
    #     ensemble = Ensemble()
    #     ensemble.catalogs = [type('obj', (object,), {"name": f"cat{i}"})()]
    #     source_model.add_ensemble(ensemble)

    data_selector_view = DataSelectorView()
    data_selector_view.setModel(source_model)

    proxy_model = CanvasProxyModel()
    proxy_model.setSourceModel(source_model)
    results_view = ResultsTabView()
    results_view.setModel(proxy_model)

    list_view = QListView()
    list_view.setModel(proxy_model)

    widget = QSplitter()
    widget.addWidget(data_selector_view)
    widget.addWidget(results_view)
    widget.addWidget(list_view)

    window = QMainWindow()
    window.setCentralWidget(widget)
    window.show()

    app.exec()