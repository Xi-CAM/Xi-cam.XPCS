from qtpy.QtCore import Qt, QIdentityProxyModel, QModelIndex, QPersistentModelIndex, QSortFilterProxyModel
from qtpy.QtGui import QStandardItemModel

from xicam.core.msg import logMessage, WARNING
from xicam.core.workspace import WorkspaceDataType, Ensemble
from xicam.core.intents import Intent
from xicam.gui.workspace.models import CheckableItem

from xicam.XPCS.projectors.nexus import project_nxXPCS

# View should destroy / disown canvases when they have no Intents.
# widget.setParent(None)

# CanvasView's model is the proxyModel (attached to tree source model)
# CanvasView manages canvases
# Canvases it will display are the top 4 in the proxy model (e.g)
# Using selected layout, puts canvas widgets into layout
# needs bookkeeping for the canvas widgets (if layout changes)

# View -> CanvasProxy -> IntentProxy -> EnsembleModel




# ask Dan what common functionality should be required in a abstract canvas manager base class
# what

class CanvasManager:
    def __init__(self):
        ...

    def canvas_from_intent(self, intent):
        ...

    def drop_canvas(self, key):
        ...


class XicamCanvasManager(CanvasManager):
    def __init__(self):
        super(XicamCanvasManager, self).__init__()

    def canvas_from_index(self, index: QModelIndex):
        # Canvas exists for index, return
        canvas = index.data(EnsembleModel.canvas_role)
        if canvas:
            return canvas

        # There is another canvas we know about we should use
        for match_index in self.all_intent_indexes(index.model()):
            if self.is_matching_canvas_type(index, match_index):
                return match_index.model().data(match_index, EnsembleModel.canvas_role)

        # Does not exist, create new canvas and return
        intent = index.model().data(index, EnsembleModel.object_role)
        from xicam.plugins import manager as pluginmanager
        canvas_name = intent.canvas
        canvas = pluginmanager.get_plugin_by_name(canvas_name, "IntentCanvasPlugin")()
        index.model().setData(index, canvas, EnsembleModel.canvas_role)
        # canvas.render(intent)
        return canvas

    @classmethod
    def all_intent_indexes(cls, model: QStandardItemModel, parent_index=None):
        if parent_index is None:
            parent_index = model.invisibleRootItem().index()

        for row in range(model.rowCount(parent_index)):
            child_index = model.createIndex(row, 0, parent_index)
            data_type = model.data(child_index, EnsembleModel.data_type_role)
            if data_type is WorkspaceDataType.Intent:
                yield child_index
            elif model.hasChildren(child_index):
                yield from cls.all_intent_indexes(model, child_index)

    def is_matching_canvas_type(self, index: QModelIndex, match_index: QModelIndex):
        match_intent = match_index.model().data(EnsembleModel.object_role)
        intent = index.model().data(EnsembleModel.object_role)
        assert isinstance(intent, Intent)
        assert isinstance(match_intent, Intent)

        match_canvas_type_string = match_intent.canvas.get("qt")
        intent_canvas_type_string = intent.canvas.get("qt")

        if intent_canvas_type_string != match_canvas_type_string:
            return False

        if intent.match_key != match_intent.match_key:
            return False

        return True


class EnsembleModel(QStandardItemModel):
    object_role = Qt.UserRole + 1
    data_type_role = Qt.UserRole + 2
    canvas_role = Qt.UserRole + 3

    """Model that stores Ensembles.

    Each workspace may store multiple Catalogs.
    """
    def __init__(self, *args, **kwargs):
        super(EnsembleModel, self).__init__(*args, **kwargs)
        self.dataChanged.connect(self.DEBUG)

    def DEBUG(self, *args, **kwargs):
        print(f"Ensemble dataChanged emitted\n\t{args}\n\t{kwargs}")

    def add_ensemble(self, ensemble: Ensemble):
        ensemble_item = CheckableItem()
        ensemble_item.setData(ensemble.name, Qt.DisplayRole)
        ensemble_item.setData(ensemble, self.object_role)
        ensemble_item.setData(WorkspaceDataType.Ensemble, self.data_type_role)

        for catalog in ensemble.catalogs:
            catalog_item = CheckableItem()
            catalog_name = getattr(catalog, "name", "catalog")
            catalog_item.setData(catalog_name, Qt.DisplayRole)
            catalog_item.setData(catalog, self.object_role)
            catalog_item.setData(WorkspaceDataType.Catalog, self.data_type_role)

            try:
                intents = project_nxXPCS(catalog)
                for intent in intents:
                    intent_item = CheckableItem()
                    intent_item.setData(intent.name, Qt.DisplayRole)
                    intent_item.setData(intent, self.object_role)
                    intent_item.setData(WorkspaceDataType.Intent, self.data_type_role)
                    catalog_item.appendRow(intent_item)
            except AttributeError as e:
                logMessage(e, level=WARNING)

            ensemble_item.appendRow(catalog_item)

        self.appendRow(ensemble_item)

    def remove_ensemble(self, ensemble):
        # TODO
        raise NotImplementedError

    def rename_ensemble(self, ensemble, name):
        found_ensemble_items = self.findItems(ensemble.name)
        if found_ensemble_items:
            ensemble_item = found_ensemble_items[0]
            # Better way to do this (CatalogItem.setData can auto rename)
            ensemble = ensemble_item.data(Qt.UserRole)
            ensemble.name = name
            ensemble_item.setData(name, Qt.DisplayRole)


class CanvasProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super(CanvasProxyModel, self).__init__()
        self.setRecursiveFilteringEnabled(True)
        self.canvas_manager = XicamCanvasManager()

        # self.sourceModel().dataChanged.connect(self.DEBUG)

    def DEBUG(self, *args, **kwargs):
        print(f"CanvasProxyModel dataChanged emitted\n\t{args}\n\t{kwargs}")

    def data(self, index, role=Qt.DisplayRole):
        print("CanvasProxyModel.data")
        if role == EnsembleModel.canvas_role:
            return self.canvas_manager.canvas_from_index(index)
        return super(CanvasProxyModel, self).data(index, role)

    def filterAcceptsRow(self, row, parent):
        print("CanvasProxyModel.filterAcceptsRow")
        index = self.sourceModel().index(row, 0, parent)
        print(f"\tindex: {index}")
        data_type_role = index.data(role=self.sourceModel().data_type_role)
        print(f"\tdata_type_role: {data_type_role}")
        parent_check_state = self.sourceModel().data(parent, Qt.CheckStateRole)
        print(f"\tparent.isValid(): {parent.isValid()}")
        print(f"\tparent_check_state: {parent_check_state}")

        temp_ret_val = False

        if data_type_role == WorkspaceDataType.Intent and parent_check_state != Qt.Unchecked:
            temp_ret_val = True

        print(f"\tRETURN: {temp_ret_val}\n")
        return temp_ret_val


if __name__ == "__main__":
    from databroker.in_memory import BlueskyInMemoryCatalog
    from qtpy.QtWidgets import QApplication, QMainWindow, QSplitter, QListView
    from xicam.SAXS.widgets.views import ResultsTabView, DataSelectorView
    from xicam.XPCS.ingestors import ingest_nxXPCS
    from xicam.gui.windows.mainwindow import XicamMainWindow


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
    #     workspace = Ensemble()
    #     workspace.catalogs = [type('obj', (object,), {"name": f"cat{i}"})()]
    #     source_model.add_ensemble(workspace)

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

    window = XicamMainWindow()
    window.setCentralWidget(widget)
    window.show()

    app.exec()


class _CanvasProxyModel(QIdentityProxyModel):
    """Maps data to appropriate render target."""
    def __init__(self, canvas_manager, *args, **kwargs):
        super(_CanvasProxyModel, self).__init__(*args, **kwargs)
        self._canvas_manager = CanvasManager()
        self._canvas_to_indexes_map = {}   # Dict[HintCanvas, List[QPersistentModelIndex]]

    def canvas_from_index(self, index: QModelIndex):
        canvas = self.data(index, self.CanvasRole)
        if canvas is not None:
            return canvas
        else:
            canvas = self.create_canvas(index)
        return canvas

    def create_canvas(self, index: QModelIndex):
        # canvas =
        ...

    # @staticmethod
    # def create_canvas(canvas_type, *canvas_args, **canvas_kwargs):
    #     if canvas_type:
    #         canvas = canvas_type(*canvas_args, **canvas_kwargs)
    #         return canvas

    def add_data_to_canvas(self, canvas, data: Intent, index: QPersistentModelIndex):
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
            return super(_CanvasProxyModel, self).data(index, role)

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