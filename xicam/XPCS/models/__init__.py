from collections import defaultdict
from itertools import count
from typing import Any

from qtpy.QtCore import Qt, QIdentityProxyModel, QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, \
    QItemSelectionRange
from qtpy.QtGui import QStandardItemModel

from xicam.core.msg import logMessage, WARNING
from xicam.core.workspace import WorkspaceDataType#, Ensemble
from xicam.core.intents import Intent
from xicam.plugins import manager as pluginmanager
from xicam.gui.models.treemodel import TreeModel, TreeItem

from xicam.XPCS.projectors.nexus import project_nxXPCS


class CanvasManager:
    def __init__(self):
        ...

    def canvas_from_intent(self, intent):
        ...

    def drop_canvas(self, key):
        ...

    # def render(self, canvas, intent):
    #     canvas.render(intent)

    def canvas_from_registry(self, canvas_name, registry):
        ...

    # ImageIntentCanvas <- ImageWithRoiIntentCanvas
    # or (preferred) add logic in the ImageIntentCanvas render method


class XicamCanvasManager(CanvasManager):
    def __init__(self):
        super(XicamCanvasManager, self).__init__()

    def canvas_from_registry(self, canvas_name, registry):
        return registry.get_plugin_by_name(canvas_name, "IntentCanvasPlugin")()

    def drop_canvas(self, key: QModelIndex):
        intent = key.data(EnsembleModel.object_role)
        canvas = key.data(EnsembleModel.canvas_role)
        if canvas:
            drop_completely = canvas.unrender(intent)

    def canvas_from_row(self, row: int, model):
        self.canvas_from_index(model.index(row, 0))

    def canvas_from_index(self, index: QModelIndex):
        if not index.isValid():
            return None

        # Canvas exists for index, return
        # TODO: index should not be 'Ensemble 1'... this causes recursing into canvas_from_index...
        canvas = index.data(EnsembleModel.canvas_role)
        if canvas:
            return canvas

        # There is another canvas we know about we should use
        for match_index in self.all_intent_indexes(index.model()):
            if self.is_matching_canvas_type(index, match_index):
                canvas = match_index.model().data(match_index, EnsembleModel.canvas_role)
                if canvas is not None:
                    return canvas

        # Does not exist, create new canvas and return
        intent = index.model().data(index, EnsembleModel.object_role)
        canvas_name = intent.canvas
        registry = pluginmanager
        canvas = self.canvas_from_registry(canvas_name, registry)

        index.model().setData(index, canvas, EnsembleModel.canvas_role)
        # TODO why doesn't above modify index.data(EnsembleMOdel.canvas_role)?
        index.model()
        # canvas.render(intent)
        return canvas

    @classmethod
    def all_intent_indexes(cls, model: TreeModel, parent_index=None):
        if parent_index is None:
            parent_index = model.index(0, 0, QModelIndex())

        for row in range(model.rowCount(parent_index)):
            child_index = model.index(row, 0, parent_index)
            data_type = model.data(child_index, EnsembleModel.data_type_role)
            if data_type is WorkspaceDataType.Intent:
                yield child_index
            elif model.hasChildren(child_index):
                yield from cls.all_intent_indexes(model, child_index)

    def is_matching_canvas_type(self, index: QModelIndex, match_index: QModelIndex):
        match_intent = match_index.data(EnsembleModel.object_role)
        intent = index.data(EnsembleModel.object_role)
        assert isinstance(intent, Intent)
        assert isinstance(match_intent, Intent)

        match_canvas_type_string = match_intent.canvas
        intent_canvas_type_string = intent.canvas

        if intent_canvas_type_string != match_canvas_type_string:
            return False

        if intent.match_key != match_intent.match_key:
            return False

        return True


class Ensemble:
    """Represents an organized collection of catalogs."""
    _count = count(1)

    def __init__(self, parent=None, name=""):
        # super(Ensemble, self).__init__(parent)

        self.catalogs = []
        self._name = name
        self._count = next(self._count)

    @property
    def name(self):
        if not self._name:
            self._name = f"Ensemble {self._count}"
        return self._name

    @name.setter
    def name(self, name):
        if not name:
            return
        self._name = name

    def append_catalog(self, catalog):
        self.catalogs.append(catalog)

    def append_catalogs(self, *catalogs):
        for catalog in catalogs:
            self.append_catalog(catalog)


class EnsembleModel(TreeModel):
    object_role = Qt.UserRole + 1
    data_type_role = Qt.UserRole + 2
    canvas_role = Qt.UserRole + 3

    """Model that stores Ensembles.

    Each workspace may store multiple Catalogs.
    """
    def __init__(self, parent=None):
        super(EnsembleModel, self).__init__(parent)

    def setData(self, index: QModelIndex, value: Any, role: Qt.ItemDataRole = Qt.EditRole) -> bool:
        if not index.isValid():
            return False
        item = self.getItem(index)
        if role in (self.object_role, self.canvas_role, self.data_type_role):
            item.itemData[role] = value
            # self.dataChanged.emit(index, role)
            # return True
        else:
            return super(EnsembleModel, self).setData(index, value, role)

    def add_ensemble(self, ensemble: Ensemble):
        ensemble_item = TreeItem(self.rootItem)
        # ensemble_item = ensemble
        ensemble_item.setData(ensemble.name, Qt.DisplayRole)
        ensemble_item.setData(ensemble, self.object_role)
        ensemble_item.setData(WorkspaceDataType.Ensemble, self.data_type_role)

        for catalog in ensemble.catalogs:
            catalog_item = TreeItem(ensemble_item)
            catalog_name = getattr(catalog, "name", "catalog")
            catalog_item.setData(catalog_name, Qt.DisplayRole)
            catalog_item.setData(catalog, self.object_role)
            catalog_item.setData(WorkspaceDataType.Catalog, self.data_type_role)

            try:
                intents = project_nxXPCS(catalog)
                for intent in intents:
                    intent_item = TreeItem(catalog_item)
                    intent_item.setData(intent.name, Qt.DisplayRole)
                    intent_item.setData(intent, self.object_role)
                    intent_item.setData(WorkspaceDataType.Intent, self.data_type_role)
                    catalog_item.appendChild(intent_item)
            except AttributeError as e:
                logMessage(e, level=WARNING)

            ensemble_item.appendChild(catalog_item)

        self.rootItem.appendChild(ensemble_item)

    def remove_ensemble(self, ensemble):
        # TODO
        raise NotImplementedError

    def rename_ensemble(self, ensemble, name):
        # TODO, defer to setData w/ EditRole
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

    def setSourceModel(self, model):
        super(CanvasProxyModel, self).setSourceModel(model)
        model.dataChanged.connect(self.dataChanged)
        # TODO: remove above connection, implement filterDataChanged (which then would emit data changed...)
        # model.dataChanged.connect(self.filterDataChanged)


    def filterDataChanged(self, topLeft, bottomRight, roles):
        # topLeft is the highest ancesestor of the item that was checked/unchecked
        # bottomRight is the deepest child of the item that was checked/unchecked
        # [x]            - topLeft
        #    []
        #       []                       new top left
        #       []      -- bottomRight
        #    []
        #       []                       new bottom right

        # iterate over all children of topLeft; for all of their children emit ranges
        # Map the range to the proxy model as a new Qselection... (hopefully)
        selection_range = QItemSelectionRange(topLeft, bottomRight)

        # Get a list of all intent indexes (with .selectedIndexes(), hopefully)
        selected_indexes = selection_range.indexes()

        intent_indexes = filter(lambda index: self.filterAcceptsRow(index.row(), index.parent()), selected_indexes)

        index_map = defaultdict(list)
        for index in intent_indexes:
            index_map[index.parent()].append(index)

        for indices in index_map.values():
            self.dataChanged.emit(indices[0], indices[-1], roles)

        # self.dataChanged.emit(topLeft, bottomRight, roles)

    def data(self, index, role=Qt.DisplayRole):
        if role == EnsembleModel.canvas_role:
            return self.canvas_manager.canvas_from_index(index)
        return super(CanvasProxyModel, self).data(index, role)

    def filterAcceptsRow(self, row, parent):
        index = self.sourceModel().index(row, 0, parent)
        data_type_role = index.data(role=self.sourceModel().data_type_role)
        parent_check_state = self.sourceModel().data(parent, Qt.CheckStateRole)

        temp_ret_val = False

        if data_type_role == WorkspaceDataType.Intent and parent_check_state != Qt.Unchecked:
            temp_ret_val = True

        return temp_ret_val


if __name__ == "__main__":
    from databroker.in_memory import BlueskyInMemoryCatalog
    from qtpy.QtWidgets import QApplication, QMainWindow, QSplitter, QListView, QTreeView
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

    data_selector_view = QTreeView()
    data_selector_view.setModel(source_model)

    proxy_model = CanvasProxyModel()
    proxy_model.setSourceModel(source_model)
    proxy_view = QListView()
    proxy_view.setModel(proxy_model)

    widget = QSplitter()
    widget.addWidget(data_selector_view)
    widget.addWidget(proxy_view)


    window = QMainWindow()
    window.setCentralWidget(widget)
    window.show()

    app.exec()