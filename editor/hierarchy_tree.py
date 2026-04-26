"""
HierarchyTree - QTreeWidget con drag-drop para reordenar la jerarquía padre-hijo.
"""
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QAbstractItemView, QMenu
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDropEvent


class HierarchyTree(QTreeWidget):
    reparent_requested = pyqtSignal(int, object)   # child_id, parent_id | None
    delete_requested   = pyqtSignal(int)            # entity_id a eliminar
    rename_requested   = pyqtSignal(int)            # entity_id a renombrar

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.setStyleSheet(
            "QTreeWidget { background: #1e1e1e; color: #dcdcdc;"
            "  border: none; outline: none; }"
            "QTreeWidget::item { padding: 3px; }"
            "QTreeWidget::item:selected { background: #4a7cb8; }"
            "QTreeWidget::item:hover { background: #333; }"
            "QTreeWidget::branch { background: #1e1e1e; }"
        )

    # ------------------------------------------------------------------ #
    def dropEvent(self, event: QDropEvent) -> None:
        dragged = self.currentItem()
        if dragged is None:
            event.ignore()
            return

        pos = event.position().toPoint()
        target = self.itemAt(pos)

        child_id = dragged.data(0, Qt.ItemDataRole.UserRole)

        if (target is not None
                and self.dropIndicatorPosition()
                    == QAbstractItemView.DropIndicatorPosition.OnItem):
            parent_id = target.data(0, Qt.ItemDataRole.UserRole)
        else:
            parent_id = None

        if child_id != parent_id:
            self.reparent_requested.emit(child_id, parent_id)

        event.accept()

    # ------------------------------------------------------------------ #
    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        entity_id = item.data(0, Qt.ItemDataRole.UserRole)

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #252525; color: #dcdcdc; border: 1px solid #3a3a3a; }"
            "QMenu::item { padding: 5px 20px 5px 12px; }"
            "QMenu::item:selected { background: #4a7cb8; }"
            "QMenu::separator { background: #3a3a3a; height: 1px; margin: 3px 6px; }"
        )
        rename_act = menu.addAction("✏  Renombrar")
        clear_act  = menu.addAction("Quitar padre  (hacer raíz)")
        menu.addSeparator()
        delete_act = menu.addAction("Eliminar entidad")

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == rename_act:
            self.rename_requested.emit(entity_id)
        elif chosen == clear_act:
            self.reparent_requested.emit(entity_id, None)
        elif chosen == delete_act:
            self.delete_requested.emit(entity_id)
