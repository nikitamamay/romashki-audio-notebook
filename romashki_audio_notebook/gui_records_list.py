import typing

from PyQt5 import QtCore, QtWidgets, QtGui

import traceback
import os
import sys
import math

from . import audio
from . import record
from .record import Record

from . import gui_def

from . import tts_whisper


class Pixmaps:
    # _recording: QtGui.QPixmap|None = None
    _record: QtGui.QPixmap|None = None

    @staticmethod
    def record() -> QtGui.QPixmap:
        if Pixmaps._record is None:
            Pixmaps._record = QtGui.QPixmap(gui_def.ICON_RECORD_SYMBOL)
        return Pixmaps._record  # type: ignore

    # @staticmethod
    # def recording() -> QtGui.QPixmap:
    #     if Pixmaps._recording is None:
    #         Pixmaps._recording = QtGui.QPixmap(gui_def.ICON_RECORDING_16)
    #     return Pixmaps._recording



class RecordWidget(QtWidgets.QWidget):

    def __init__(
            self,
            record: Record,
            parent = None,
            ) -> None:
        super().__init__(parent)
        # self.setFixedHeight(30)

        f = self.font()
        f.setPointSize(8)
        self.setFont(f)

        self.italic_font = self.font()
        self.italic_font.setPointSize(8)
        self.italic_font.setItalic(True)

        self._record: Record = record

        self._file_basename: str = ""
        self._preview_text: str = ""

        self.update_record_state()

    def minimumSizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(90, 30)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(200, 30)

    def paintEvent(self, event: QtGui.QPaintEvent | None) -> None:
        painter = QtGui.QPainter(self)
        painter.setPen(QtWidgets.qApp.palette().color(QtGui.QPalette.ColorRole.WindowText))
        painter.drawPixmap(1, 1, 14, 14, Pixmaps.record())

        fm = self.fontMetrics()
        fm2 = QtGui.QFontMetrics(self.italic_font)

        duration_text = self._record.format_duration()
        duration_text_w = fm.width(duration_text)

        painter.drawText(self.width() - duration_text_w - 2, 12, duration_text)

        name_text = fm.elidedText(self._file_basename, QtCore.Qt.TextElideMode.ElideLeft, self.width() - 16 - 2 - 2 - duration_text_w - 2)
        painter.drawText(18, 12, name_text)

        painter.setPen(QtWidgets.qApp.palette().color(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText))
        painter.setFont(self.italic_font)
        preview_text = fm2.elidedText(self._preview_text, QtCore.Qt.TextElideMode.ElideRight, self.width())
        painter.drawText(2, 27, preview_text)

    def update_record_state(self):
        self._file_basename = os.path.basename(self._record.audio_filename)
        self._preview_text = "< no text >" if self._record.text == "" else self._record.text.replace("\n", " ").strip()
        self.update()



class RecordsListWidget(QtWidgets.QWidget):
    insert_text_requested = QtCore.pyqtSignal(list)
    """ `def insert_text_requested(records: list[Record]) -> None: ...` """
    remove_to_trash_requested = QtCore.pyqtSignal(list)
    """ `def remove_to_trash_requested(records: list[Record]) -> None: ...` """
    reload_requested = QtCore.pyqtSignal()
    """ `def reload_requested() -> None: ...` """
    show_in_folder_requested = QtCore.pyqtSignal(list)
    """ `def show_in_folder_requested(records: list[Record]) -> None: ...` """

    class ItemDataRole:
        RecordObject = 101

    def __init__(self, parent = None) -> None:
        super().__init__(parent)
        # self.setMinimumWidth(130)
        # self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Ignored)

        self.list_widget = QtWidgets.QListWidget(self)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.itemDoubleClicked.connect(self._item_dbl_clicked)
        self.list_widget.setSortingEnabled(True)
        # self.list_widget.contex.connect(lambda *args: print(args))

        self.list_widget_model: QtCore.QAbstractItemModel = self.list_widget.model()  # type: ignore

        self._layout = QtWidgets.QGridLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self.list_widget)
        self.setLayout(self._layout)

        self._action_insert_text = QtWidgets.QAction("Insert text")
        self._action_insert_text.triggered.connect(self._insert_text_for_selected_items)

        self._action_show_in_folder = QtWidgets.QAction("Show in folder")
        self._action_show_in_folder.triggered.connect(self._show_in_folder_for_selected_items)

        self._action_reload = QtWidgets.QAction("Reload")
        self._action_reload.triggered.connect(self._reload)

        self._action_remove_to_trash = QtWidgets.QAction("Remove to trash")
        self._action_remove_to_trash.triggered.connect(self._remove_to_trash_selected_items)

        self._context_menu = QtWidgets.QMenu(self)
        self._context_menu.addAction(self._action_insert_text)
        self._context_menu.addAction(self._action_show_in_folder)
        self._context_menu.addAction(self._action_reload)
        self._context_menu.addAction(self._action_remove_to_trash)

    # def minimumSizeHint(self) -> QtCore.QSize:
    #     return QtCore.QSize(120, 200)

    # def sizeHint(self) -> QtCore.QSize:
    #     return QtCore.QSize(250, 200)

    def add_record(self, r: Record) -> None:
        item = QtWidgets.QListWidgetItem()
        item.setData(RecordsListWidget.ItemDataRole.RecordObject, r)
        w = RecordWidget(r)
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, w)
        item.setSizeHint(w.minimumSizeHint())
        self.update_records_state([r])

    def remove_record(self, r: Record) -> None:
        item = self.get_item_by_record(r)
        if item is not None:
            self.list_widget_model.removeRow(self.list_widget.indexFromItem(item).row())

    def get_selected_items(self) -> list[QtWidgets.QListWidgetItem]:
        return self.list_widget.selectedItems()

    def get_one_selected_items(self) -> QtWidgets.QListWidgetItem|None:
        si = self.list_widget.selectedItems()
        if len(si) != 1:
            return None
        return si[0]

    def get_selected_records(self) -> list[Record]:
        return list(map(lambda item: item.data(RecordsListWidget.ItemDataRole.RecordObject), self.get_selected_items()))

    def get_all_items(self) -> list[QtWidgets.QListWidgetItem]:
        return list(self.iterate_all_items())

    def iterate_all_items(self) -> typing.Generator[QtWidgets.QListWidgetItem, None, None]:
        for i in range(self.list_widget_model.rowCount()):
            index = self.list_widget_model.index(i, 0)
            item = self.list_widget.itemFromIndex(index)
            assert item is not None
            yield item

    def get_record_to_item_mapping(self) -> dict[Record, QtWidgets.QListWidgetItem]:
        mapping = {}
        for item in self.iterate_all_items():
            r: Record = item.data(RecordsListWidget.ItemDataRole.RecordObject)
            mapping[r] = item
        return mapping

    def get_item_by_record(self, r: Record) -> QtWidgets.QListWidgetItem|None:
        for item in self.iterate_all_items():
            if item.data(RecordsListWidget.ItemDataRole.RecordObject) == r:
                return item
        return None

    def update_records_state(self, records: typing.Sequence[Record] = []) -> None:
        if len(records) == 0:
            items = self.get_all_items()
        else:
            items = []
            r_to_i = self.get_record_to_item_mapping()
            for r in records:
                i = r_to_i.get(r, None)
                if i is not None:
                    items.append(i)

        for item in items:
            rw: RecordWidget = self.list_widget.itemWidget(item)
            assert isinstance(rw, RecordWidget)
            rw.update_record_state()
            r: Record = item.data(RecordsListWidget.ItemDataRole.RecordObject)
            assert r is not None
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, f"{tts_whisper.render_file_size(r.get_audio_data_size())}")

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent | None) -> None:
        if event is not None:
            self._context_menu.exec(event.globalPos())

            # # sometimes does not work properly: there is selection, but actions are disabled
            # has_selection = self.list_widget.selectionModel().hasSelection()  # type: ignore
            # self._action_insert_text.setEnabled(has_selection)
            # self._action_remove_to_trash.setEnabled(has_selection)

            event.accept()
        return super().contextMenuEvent(event)

    def _sort_items(self, order: int = QtCore.Qt.SortOrder.DescendingOrder) -> None:
        for i, item in enumerate(sorted(
            self.get_all_items(),
            key = lambda item: item.data(RecordsListWidget.ItemDataRole.RecordObject).audio_filename,
            reverse=order == QtCore.Qt.SortOrder.DescendingOrder
        )):
            self.list_widget_model.moveRow(
                QtCore.QModelIndex(), self.list_widget.indexFromItem(item).row(),
                QtCore.QModelIndex(), i)

    def _insert_text_for_selected_items(self) -> None:
        records = self.get_selected_records()
        records.sort(key=lambda r: r.audio_filename)  # sorting to make older records be inserted after newer ones
        self.insert_text_requested.emit(records)

    def _reload(self) -> None:
        self.reload_requested.emit()

    def _remove_to_trash_selected_items(self) -> None:
        self.remove_to_trash_requested.emit(self.get_selected_records())

    def _show_in_folder_for_selected_items(self) -> None:
        self.show_in_folder_requested.emit(self.get_selected_records())

    def _item_dbl_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        r = item.data(RecordsListWidget.ItemDataRole.RecordObject)
        if r is not None:
            self.insert_text_requested.emit([r])





if __name__ == "__main__":
    def main():
        app = QtWidgets.QApplication([])

        r1 = Record.from_file(r"D:\programms\Python\2025\romashki-audio-notebook\test4-for-v3\2026.05.03-13.56.23.wav")
        r2 = Record.from_file(r"D:\programms\Python\2025\romashki-audio-notebook\test3-whispercpp\mysample1.wav")

        # w = RecordWidget(r1)
        # # w.resize(400, 300)
        # # w.update_record_state()
        w = RecordsListWidget()
        w.add_record(r1)
        w.add_record(r2)

        w.show()

        app.exec()

    main()

