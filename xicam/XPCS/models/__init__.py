import weakref
from collections import defaultdict
from itertools import count
from typing import Any, List, Iterable, Callable

from qtpy.QtCore import Qt, QIdentityProxyModel, QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, \
    QItemSelectionRange, QAbstractItemModel
from qtpy.QtGui import QStandardItemModel

from xicam.core.data.bluesky_utils import display_name
from xicam.core.msg import logMessage, WARNING
from xicam.core.workspace import WorkspaceDataType
from xicam.core.intents import Intent
from xicam.plugins import manager as pluginmanager
from xicam.gui.models.treemodel import TreeModel, TreeItem

from xicam.XPCS.projectors.nexus import project_nxXPCS
from xicam.plugins.intentcanvasplugin import IntentCanvas


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
    """TreeModel that stores Ensembles.

    Defines custom roles:
    object_role: contains a reference to item's data (this is the custom UserRole commonly used as Qt.UserRole + 1)
    data_type_role: indicates what WorkspaceDataType the item is
    canvas_role: reference to an associated canvas (may not be set if not applicable)

    """
    object_role = Qt.UserRole + 1
    data_type_role = Qt.UserRole + 2
    canvas_role = Qt.UserRole + 3

    def __init__(self, parent=None):
        super(EnsembleModel, self).__init__(parent)

    def setData(self, index: QModelIndex, value: Any, role: Qt.ItemDataRole = Qt.EditRole) -> bool:
        if not index.isValid():
            return False
        item = self.getItem(index)
        # if role in (self.object_role, self.canvas_role, self.data_type_role):
            # item.itemData[role] = value
        # if role == Qt.CheckStateRole:
        #     success = super(EnsembleModel, self).setData(index, True, self.state_changed_role)
        #     if not success:
        #         return False
        return super(EnsembleModel, self).setData(index, value, role)

    def add_ensemble(self, ensemble: Ensemble, projector: Callable):
        ensemble_item = TreeItem(self.rootItem)
        # ensemble_item = ensemble
        ensemble_item.setData(ensemble.name, Qt.DisplayRole)
        ensemble_item.setData(ensemble, self.object_role)
        ensemble_item.setData(WorkspaceDataType.Ensemble, self.data_type_role)

        for catalog in ensemble.catalogs:
            catalog_item = TreeItem(ensemble_item)
            catalog_name = display_name(catalog)
            catalog_item.setData(catalog_name, Qt.DisplayRole)
            catalog_item.setData(catalog, self.object_role)
            catalog_item.setData(WorkspaceDataType.Catalog, self.data_type_role)

            try:
                intents = projector(catalog)
                for intent in intents:
                    intent_item = TreeItem(catalog_item)
                    intent_item.setData(intent.item_name, Qt.DisplayRole)
                    intent_item.setData(intent, self.object_role)
                    intent_item.setData(WorkspaceDataType.Intent, self.data_type_role)
                    catalog_item.appendChild(intent_item)
            except AttributeError as e:
                logMessage(e, level=WARNING)

            ensemble_item.appendChild(catalog_item)

        self.rootItem.appendChild(ensemble_item)
        self.layoutChanged.emit()

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


class IntentsModel(QAbstractItemModel):
    def __init__(self):
        super(IntentsModel, self).__init__()

        self._source_model: QAbstractItemModel = None
        self._source_indexes = []

    def _intent_source_indexes_gen(self):
        for ensemble_row in range(self._source_model.rowCount(QModelIndex())):
            ensemble_index = self._source_model.index(ensemble_row, 0)
            for run_row in range(self._source_model.rowCount(ensemble_index)):
                run_index = self._source_model.index(run_row, 0, ensemble_index)
                for intent_row in range(self._source_model.rowCount(run_index)):
                    intent_index = self._source_model.index(intent_row, 0, run_index)
                    if intent_index.data(Qt.CheckStateRole) != Qt.Unchecked:
                        yield intent_index

    @property
    def _intent_source_indexes(self):
        if not self._source_indexes:
            self._source_indexes = list(self._intent_source_indexes_gen())
        return self._source_indexes

    def setSourceModel(self, model):
        self._source_model = model
        self._source_model.dataChanged.connect(self.sourceDataChanged)

    def sourceDataChanged(self, topLeft: QModelIndex, bottomRight: QModelIndex, roles: Iterable[int] = ...) -> None:
        # Invalidate cache
        self._source_indexes.clear()

        # TODO: translate source model indexes into intentsmodel indexes and emit those rather than emit all
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount()-1, 0), roles)

    def sourceModel(self):
        return self._source_model

    def index(self, row, column, parent=QModelIndex()):
        try:
            intent_index = self._intent_source_indexes[row]  # FIXME: THIS IS KINDA INEFFICIENT
            i = self.createIndex(row, column, intent_index)
            return i

        # FIXME: target specific exception or handle differently
        except Exception:
            return QModelIndex()

    def parent(self, child):
        return QModelIndex()

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(self._intent_source_indexes)
        else:
            return 0

    def columnCount(self, parent):
        if not parent.isValid():
            return 1
        else:
            return 0

    def data(self, index, role=Qt.DisplayRole):
        # print(f"IntentsModel.data({index.data()}, {role} -> {self._source_model.data(index, role)}")

        if not index.isValid():
            return None

        elif role == Qt.DisplayRole:
            intent = index.internalPointer()  # must call because its a weakref
            return intent.item_name

        elif role == EnsembleModel.object_role:
            return index.internalPointer()

        return None


class XicamCanvasManager(CanvasManager):
    def __init__(self):
        super(XicamCanvasManager, self).__init__()

    def canvases(self, model: IntentsModel) -> List[IntentCanvas]:
        """Retrieve all canvases from a given model."""
        # Create a mapping from canvas to rows to get unique canvas references.
        canvas_to_row = defaultdict(list)
        for row in range(model.rowCount()):
            canvas = self.canvas_from_row(row, model)
            canvas_to_row[canvas].append(row)
        # Only return canvases if they have at least one associated row (sanity check).
        return [canvas for canvas, rows in canvas_to_row.items() if len(rows)]

    def canvas_from_registry(self, canvas_class_name, registry, canvas_name):
        return registry.get_plugin_by_name(canvas_class_name, "IntentCanvasPlugin")(canvas_name=canvas_name)

    def drop_canvas(self, key: QModelIndex):
        intent = key.data(EnsembleModel.object_role)
        canvas = key.data(EnsembleModel.canvas_role)
        if canvas:
            drop_completely = canvas.unrender(intent)

    def canvas_from_row(self, row: int, model, parent_index=QModelIndex()):
        # TODO: model.index v. model.sourceModel().index (i.e. should this only be Proxy Model, or EnsembleModel, or both)?
        return self.canvas_from_index(model.index(row, 0, parent_index).internalPointer())

    def canvas_from_index(self, index: QModelIndex):
        if not index.isValid():
            return None

        if index.data(EnsembleModel.data_type_role) != WorkspaceDataType.Intent:
            print(f'WARNING: canvas_from_index index {index} is not an intent')
            return None

        # Canvas exists for index, return
        # TODO: in tab view, with multiple intents selected (e.g. 2 rows checked),
        #       non-0 row intents (every intent except first) does not have a valid object in canvas_role
        canvas = index.model().data(index, EnsembleModel.canvas_role)
        if canvas:
            return canvas

        # There is another canvas we know about we should use
        for match_index in self.all_intent_indexes(index.model()):
            if self.is_matching_canvas_type(index, match_index):
                canvas = match_index.model().data(match_index, EnsembleModel.canvas_role)
                if canvas is not None:
                    index.model().setData(index, canvas, EnsembleModel.canvas_role)
                    return canvas

        # Does not exist, create new canvas and return
        intent = index.model().data(index, EnsembleModel.object_role)
        canvas_class_name = intent.canvas
        registry = pluginmanager
        canvas = self.canvas_from_registry(canvas_class_name, registry, intent.canvas_name)

        index.model().setData(index, canvas, EnsembleModel.canvas_role)
        return canvas

    @classmethod
    def all_intent_indexes(cls, model: TreeModel, parent_index=QModelIndex()):

        for row in range(model.rowCount(parent_index)):
            child_index = model.index(row, 0, parent_index)
            data_type = model.data(child_index, EnsembleModel.data_type_role)
            if data_type is WorkspaceDataType.Intent:
                yield child_index
            elif model.hasChildren(child_index):
                yield from cls.all_intent_indexes(model, child_index)
        print()

    def is_matching_canvas_type(self, index: QModelIndex, match_index: QModelIndex):
        match_intent = match_index.data(EnsembleModel.object_role)
        intent = index.data(EnsembleModel.object_role)
        if not isinstance(intent, Intent):
            print(f"WARNING: during matching, index {index.data} is not an Intent")
            return False
        if not isinstance(match_intent, Intent):
            print(f"WARNING: during matching, match_index {index.data} is not an Intent")
            return False
        # assert isinstance(intent, Intent)
        # assert isinstance(match_intent, Intent)

        match_canvas_type_string = match_intent.canvas
        intent_canvas_type_string = intent.canvas

        if intent_canvas_type_string != match_canvas_type_string:
            return False

        if intent.match_key != match_intent.match_key:
            return False

        return True
