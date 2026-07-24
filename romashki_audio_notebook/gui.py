import typing

from PyQt5 import QtCore, QtWidgets, QtGui

import traceback
import os
import sys
import io
import math

import threading

from . import config
from . import audio
from . import tts_whisper

from . import prevent_sleep

from .gui_def import *
from .gui_logger_window import LoggerStringIO, LoggerWidget
from .gui_elided_label import ElidableLabel
from .gui_audio_vis import AudioVisualizerWidget
from .gui_settings import SettingsWindow
from .gui_records_list import RecordWidget, RecordsListWidget

from . import record
from .record import Record

from . import show_in_folder

from send2trash import send2trash





class States:
    Idle           = 0b00000000
    Recording      = 0b00000001
    Analyzing      = 0b00000010
    Loading        = 0b10000000
    # ReadyForRecord = 0b01000000
    BITMASK_1      = 0b11111111

    @staticmethod
    def set(states: int, flag: int, value: bool) -> int:
        if value:
            return states | flag
        else:
            return states & (States.BITMASK_1 - flag)


def get_state_icon(state: int):
    if state == States.Idle:
        return QtGui.QIcon(ICON_APP)

    # if state & States.ReadyForRecord:
    #     return QtGui.QIcon(ICON_READY_FOR_RECORD)

    if state & States.Loading:
        return QtGui.QIcon(ICON_LOADING)

    if state & States.Recording and state & States.Analyzing:
        return QtGui.QIcon(ICON_RECORDING_AND_ANALYZING)

    if state & States.Recording:
        return QtGui.QIcon(ICON_RECORDING)

    if state & States.Analyzing:
        return QtGui.QIcon(ICON_ANALYZING)

    raise Exception(f"Unknown state: {state}")


class MicButton(QtWidgets.QPushButton):
    def __init__(self):
        super().__init__()
        self.set_state(States.Idle)

    def set_state(self, state: int) -> None:
        if state & States.Recording:
            return self.setIcon(QtGui.QIcon(ICON_STOP))
        else:
            return self.setIcon(QtGui.QIcon(ICON_READY_FOR_RECORD))


class TrayIcon(QtWidgets.QSystemTrayIcon):
    tray_icon_triggered = QtCore.pyqtSignal()
    application_exit_requested = QtCore.pyqtSignal()

    def __init__(self, parent = None):
        super().__init__(parent)
        self._menu = QtWidgets.QMenu()

        self._menu.addSeparator()
        self._menu.addAction("Exit", self.application_exit_requested.emit)
        # self._menu.aboutToShow.connect()
        self.setContextMenu(self._menu)

        self.activated.connect(self._activated_handler)  # clicked

    def _activated_handler(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            self.tray_icon_triggered.emit()

    def set_state_icon(self, state: int) -> None:
        self.setIcon(get_state_icon(state))


class TextArea(QtWidgets.QPlainTextEdit):
    def __init__(self, parent = None) -> None:
        super().__init__(parent)

        set_monospace_font(self.font, self.setFont)

    def copy(self) -> None:
        tc = self.textCursor()
        text = tc.selectedText()
        text = text.replace("\u2029", "\n")  # \u2029 is a Paragraph Separator symbol
        cb = QtWidgets.qApp.clipboard()
        if cb is None:
            print("Error: QtWidgets.qApp.clipboard() is None")
            return
        cb.setText(text, QtGui.QClipboard.Mode.Clipboard)

    def cut(self) -> None:
        self.copy()
        self.textCursor().removeSelectedText()

    def keyPressEvent(self, event: QtGui.QKeyEvent | None) -> None:
        if event is not None:
            if event.matches(QtGui.QKeySequence.StandardKey.Cut):
                self.cut()
                event.accept()
                return
            if event.matches(QtGui.QKeySequence.StandardKey.Copy):
                self.copy()
                event.accept()
                return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent | None) -> None:
        if event is not None:
            menu = QtWidgets.QMenu(self)

            menu.addAction("Undo", self.undo, QtGui.QKeySequence.StandardKey.Undo)
            menu.addAction("Redo", self.redo, QtGui.QKeySequence.StandardKey.Redo)
            menu.addSeparator()
            menu.addAction("Cut", self.cut, QtGui.QKeySequence.StandardKey.Cut)
            menu.addAction("Copy", self.copy, QtGui.QKeySequence.StandardKey.Copy)
            menu.addAction("Paste", self.paste, QtGui.QKeySequence.StandardKey.Paste)
            menu.addAction("Delete", self.textCursor().removeSelectedText)
            menu.addSeparator()
            menu.addAction("Select all", self.selectAll, QtGui.QKeySequence.StandardKey.SelectAll)

            menu.exec(event.globalPos())
            return
        super().contextMenuEvent(event)


class MainWindow(QtWidgets.QWidget):
    """
    Signals and slots scheme:

    ```
    signal: self._btn_recording.clicked
        -> self._recording_pressed()
        -> self._start_recording()
        -> Record_with_callback()
        => emit: self.recording_stopped

    signal: self.recording_stopped
        -> self._recording_stopped()
        => emit: self.recognize_request

    signal: self.recognize_request
        -> self._go_unrecognized()
        -> emit: self.text_recognized

    signal: self.text_recognized
        -> self._text_recognized()
        -> emit: self.recognize_request  # to ensure there is not unrecognized records
    ```
    """


    recording_stopped = QtCore.pyqtSignal(Record)
    """ `def recording_stopped(record: Record) -> None: ...` """
    text_recognized = QtCore.pyqtSignal()
    """ `def text_recognized() -> None: ...` """
    recognize_request = QtCore.pyqtSignal()
    """ `def recognize_request() -> None: ...` """
    state_updated = QtCore.pyqtSignal(str)
    """ `def state_updated(message: str) -> None: ...` """
    # error_occured = QtCore.pyqtSignal(str, str)
    # """ `def error_occured() -> None: ...` """

    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.PROGRAM_NAME)
        self.resize(400, 300)
        QtWidgets.qApp.setQuitOnLastWindowClosed(False)

        # self._thread_record = threading.Thread()
        self._total_records: list[Record] = []  # TODO перейти полностью на RecordsListWidget.iterate_records() или что-то типа того

        self._whispercpp = tts_whisper.WhisperCpp(
            config.options["whisper_executable_path"],
            config.options["whisper_model_path"],
            config.options["whisper_language"],
        )

        self._stop_request: bool = False
        self._states: int = States.Idle
        self._config_saving_timer: int = 0
        self._window_moving_timer: int = 0

        self._tray_icon = TrayIcon(self)
        self._tray_icon.tray_icon_triggered.connect(self.toggle_show_hide)
        self._tray_icon.application_exit_requested.connect(self.exit_application)

        self._btn_recording = MicButton()
        self._btn_recording.clicked.connect(self._recording_pressed)
        self._btn_recording.setIconSize(QtCore.QSize(64, 64))
        self._btn_recording.setFixedSize(70, 70)

        self._visual_widget = AudioVisualizerWidget()
        self._visual_widget.setFixedHeight(30)

        self._label_status = ElidableLabel()
        self._label_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft) # type: ignore

        self._btn_settings = QtWidgets.QPushButton(QtGui.QIcon(ICON_SETTINGS), "")
        self._btn_settings.setToolTip("Settings...")
        self._btn_settings.setFixedSize(24, 24)
        self._btn_settings.clicked.connect(self._show_settings)

        self._btn_show_records_list = QtWidgets.QPushButton(QtGui.QIcon(ICON_RECORDS_LIST), "")
        self._btn_show_records_list.setFixedSize(24, 24)
        self._btn_show_records_list.setToolTip("Toggle records list")
        self._btn_show_records_list.clicked.connect(lambda: self._set_records_list_visibility(not self._records_list_widget.isVisible()))

        self._textarea = TextArea()

        self._records_list_widget = RecordsListWidget()
        self._records_list_widget.setFixedWidth(230)
        self._records_list_widget.reload_requested.connect(self._load_from_disk)
        self._records_list_widget.remove_to_trash_requested.connect(self._remove_to_trash)
        self._records_list_widget.show_in_folder_requested.connect(self._show_in_folder)
        self._records_list_widget.insert_text_requested.connect(self._insert_text)

        self._logger_widget = LoggerWidget()

        self._layout = QtWidgets.QGridLayout()
        self._layout.setContentsMargins(5, 5, 5, 5)
        self._layout.setSpacing(5)
        self.setLayout(self._layout)
        self._layout.addWidget(self._btn_recording, 0, 0, 2, 1)
        self._layout.addWidget(self._label_status, 0, 1, 1, 1)
        self._layout.addWidget(self._btn_settings, 0, 2, 1, 1, QtCore.Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(self._btn_show_records_list, 1, 2, 1, 1)
        self._layout.addWidget(self._visual_widget, 1, 1, 1, 1)
        self._layout.addWidget(self._textarea, 2, 0, 1, 3)
        self._layout.addWidget(self._logger_widget, 3, 0, 1, 3)
        self._layout.addWidget(self._records_list_widget, 0, 3, 3, 1)

        self._config_window = SettingsWindow(self)

        self.recording_stopped.connect(self._recording_stopped)
        # self.error_occured.connect(self._error_occured)
        self.text_recognized.connect(self._text_recognized)
        self.recognize_request.connect(self._go_unrecognized)
        self.state_updated.connect(self._state_updated_handler)

        self._config_window.always_on_top_changed.connect(self.set_stays_on_top)
        self._config_window.config_changed.connect(self._config_changed)

        self.state_updated.emit("Ready to record.")

        self._set_records_list_visibility(config.options["records_list_shown"])
        self.restore_geometry_from_config()
        self.check_whisper_cpp_validity()
        self.apply_always_prevent_sleep_mode()
        self.set_stays_on_top()

        self._tray_icon.show()
        self._logger_widget.redirect_stdout()

        try:
            self._load_from_disk()
        except Exception as e:
            print(f"An error occurred while loading records from disk: {e.__class__.__name__}: {e}")

    def _recording_pressed(self):
        if not (self._states & States.Recording):
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        # if self._thread_record.is_alive():
        #     print("Cannot start recording since thread is still alive")
        #     return

        self.set_state(States.Recording, True, "Starting recording...")

        r = Record(record.get_default_filename(config.options["records_dir_path"]))
        self._total_records.append(r)
        self._records_list_widget.add_record(r)
        self._visual_widget.set_record(r)

        def on_start():
            self.set_state(States.Recording, True, "Recording...")

        def check_for_stop():
            return self._stop_request

        def on_stop(rc: int):
            print(f"on_stop() rc={rc}")
            if rc != 0:
                if r.audio_callback_recorder is not None:
                    print(r.audio_callback_recorder.get_stderr())
                print(f"Audio process exited with code {rc}. See log for details.")
            self.recording_stopped.emit(r)
            # self._visual_widget.set_record(None)

        r.record(
            check_for_stop,
            None, # on_chunk_load,
            on_start,
            on_stop,
        )
        # self._thread_record = threading.Thread(
        #     target=r.record,
        #     kwargs={
        #         "func_has_stop_request": check_for_stop,
        #         "func_data": chunk_load,
        #         "func_start": on_start,
        #         "func_exit": on_stop,
        #     }
        # )
        # self._thread_record.start()

    def _stop_recording(self):
        self._stop_request = True
        self.state_updated.emit("Stopping recording...")

    def _recording_stopped(self, r: Record):
        r.save_wav()

        self._stop_request = False
        self.set_state(States.Recording, False, "Ready to record.")

        self.recognize_request.emit()

    def _go_unrecognized(self):
        if self._states & States.Analyzing:
            self.state_updated.emit("Waiting for current analyze to complete...")
            print("Current state is analyzing, so skipping this _go_unrecognized()")
            return

        i = 0
        while i < len(self._total_records):
            r = self._total_records[i]
            if r.get_status() >= Record.Status.Recorded and r.get_status() < Record.Status.Recognizing:
                def on_end(rc: int):
                    if rc != 0:
                        if r.whisper_popen is not None:
                            if r.whisper_popen.stdout is not None:
                                try:
                                    print(r.whisper_popen.stdout.read().decode(errors="ignore"))
                                except:
                                    print(r.whisper_popen.stdout.read())
                            if r.whisper_popen.stderr is not None:
                                try:
                                    print(r.whisper_popen.stderr.read().decode(errors="ignore"))
                                except:
                                    print(r.whisper_popen.stderr.read())
                        print(f"Whisper process exited with code {rc}. See log for details.")
                    self.set_state(States.Analyzing, False, "Done analyzing.")
                    self.text_recognized.emit()

                self.set_state(States.Analyzing, True, "Analyzing...")
                r.recognize(self._whispercpp, on_end)

                break
            else:
                # print(f"skipping {r}: status={r.get_status()}, len(audio_data)={len(r.audio_data)}")
                i += 1

    def _text_recognized(self):
        i = 0
        while i < len(self._total_records):
            r = self._total_records[i]
            if r.get_status() >= Record.Status.Recognized \
                    and r.get_status() < Record.Status.TextInserted:
                try:
                    r.load_text()
                except FileNotFoundError:
                    print(f"_text_recognized(): Error: file not found for '{r.text_filename}'")
                    return
                except Exception as e:
                    print(f"_text_recognized(): Error: {e.__class__.__name__}: {e} - for {r}")
                    return

                self._insert_text([r])
                self._records_list_widget.update_records_state([r])

            i += 1

        self.recognize_request.emit()

    def show_error(self, title: str, msg: str):
        QtWidgets.QMessageBox.critical(
            self,
            title,
            f"<pre>{msg}</pre>",
        )

    def set_stays_on_top(self) -> None:
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, config.options["window_stays_on_top"])
        self._config_window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, config.options["window_stays_on_top"])
        self.show()

    def remember_geometry(self) -> None:
        x, y = self.x(), self.y()
        w, h = self.width(), self.height()
        config.options["window_geometry"] = [x, y, w, h]
        if config.options["remember_window_pos"] or config.options["remember_window_size"]:
            config.save()

    def moveEvent(self, a0):
        if self._window_moving_timer == 0:
            self._window_moving_timer = self.startTimer(2000)
        return super().moveEvent(a0)

    def resizeEvent(self, a0):
        if self._window_moving_timer == 0:
            self._window_moving_timer = self.startTimer(2000)
        return super().resizeEvent(a0)

    def save_config_delayed(self) -> None:
        if self._config_saving_timer == 0:
            self._config_saving_timer = self.startTimer(1000)

    def timerEvent(self, event: QtCore.QTimerEvent):
        if event.timerId() == self._config_saving_timer:
            config.save()
            self.killTimer(self._config_saving_timer)
            self._config_saving_timer = 0

        if event.timerId() == self._window_moving_timer:
            self.remember_geometry()
            self.killTimer(self._window_moving_timer)
            self._window_moving_timer = 0

        return super().timerEvent(event)

    def restore_geometry_from_config(self) -> None:
        x, y, w, h = config.options["window_geometry"]
        if config.options["remember_window_size"] and w != 0 and h != 0:
            self.resize(w, h)
        if config.options["remember_window_pos"] and x != 0 and y != 0:
            s = QtWidgets.qApp.screenAt(QtCore.QPoint(x, y))
            if not s is None:
                self.move(x, y)

    def closeEvent(self, event: QtGui.QCloseEvent | None) -> None:
        if config.options["do_minimize_to_tray_on_close"]:
            if event is not None:
                event.ignore()
            self.toggle_show_hide()
        else:
            self.exit_application()

    def exit_application(self):
        config.save()
        if config.options["do_remove_records_on_exit"]:
            self._remove_to_trash(self._total_records)
        QtWidgets.qApp.exit()

    def _show_settings(self) -> None:
        self._config_window.show()
        self._config_window.move(
            int(self.x() + self.width()/2 - self._config_window.width()/2),
            int(self.y() + self.height()/2 - self._config_window.height()/2),
        )

    def _config_changed(self) -> None:
        self._whispercpp.executable_path = config.options["whisper_executable_path"]
        self._whispercpp.model_path = config.options["whisper_model_path"]
        self._whispercpp.language = config.options["whisper_language"]
        self.check_whisper_cpp_validity()
        self.apply_always_prevent_sleep_mode()
        self.save_config_delayed()

    def check_whisper_cpp_validity(self) -> None:
        if not self._whispercpp.is_valid():
            self._btn_recording.setEnabled(False)
            msg = "WhisperCpp is misconfigured. Check the settings."
            self._btn_recording.setToolTip(msg)
            self.set_state(States.Loading, True, msg)
        else:
            self._btn_recording.setToolTip("")
            self.set_state(States.Loading, False, "WhisperCpp's configuration is OK.")
            self._btn_recording.setEnabled(True)

    def set_state(self, flag: int, flag_value: bool, msg: str) -> None:
        self._states = States.set(self._states, flag, flag_value)
        print(f"State updated: states=0b{bin(self._states)[2:].ljust(2, '0')} msg='{msg}'")
        self.state_updated.emit(msg)

        if not config.options["do_prevent_from_sleep_all_the_time"]:  # means: prevent from sleep only while recording
            prevent_sleep.set_prevent_sleep_mode(bool(self._states & States.Recording))

    def _state_updated_handler(self, text: str) -> None:
        self._label_status.setText(text)

        self._btn_recording.set_state(self._states)
        icon = get_state_icon(self._states)
        QtWidgets.qApp.setWindowIcon(icon)
        self._tray_icon.setIcon(icon)

    def toggle_show_hide(self) -> None:
        if self.isHidden():
            # self.show()  # doesn't bring on top if it is minimized
            self.showNormal()
        else:
            self.hide()

    def _load_from_disk(self) -> None:
        i = 0
        existing_records_files = set(map(lambda r: r.audio_filename, self._total_records))

        for filename in os.listdir(config.options["records_dir_path"]):
            if filename.endswith(".wav"):
                f_wav = os.path.join(config.options["records_dir_path"], filename)

                if not f_wav in existing_records_files:
                    try:
                        existing_records_files.add(f_wav)
                        r = Record.from_file(f_wav)
                        if r.get_status() >= Record.Status.TextLoaded: r.set_status(Record.Status.TextInserted)
                        self._total_records.append(r)
                        self._records_list_widget.add_record(r)
                        print(f"found unrecognized: {f_wav}")
                        i += 1
                    except Exception as e:
                        self.show_error(e.__class__.__name__, str(e))

        # self._records_list_widget.list_widget.sortItems()
        self._records_list_widget._sort_items()

        if i > 0:
            self._go_unrecognized()
        else:
            print(f"No unrecognized records found.")


    def _remove_to_trash(self, records: list[Record]) -> None:
        for r in records:
            self._records_list_widget.remove_record(r)
            if r in self._total_records:
                self._total_records.remove(r)

            try:
                if os.path.exists(r.audio_filename):
                    print(f"Removing file to trash: '{r.audio_filename}'")
                    send2trash([os.path.normpath(r.audio_filename)])
                if os.path.exists(r.text_filename):
                    print(f"Removing file to trash: '{r.text_filename}'")
                    send2trash([os.path.normpath(r.text_filename)])
            except Exception as e:
                print(f"_remove_to_trash(): Error: {e.__class__.__name__}: {e}")

    def _show_in_folder(self, records: list[Record]) -> None:
        if len(records) == 0:
            show_in_folder.open_folder(config.options["records_dir_path"])
        else:
            show_in_folder.show_in_folder([
                r.audio_filename
                for r in records
                if r.audio_filename != ""
            ])


    def _insert_text(self, records: list[Record]) -> None:
        tc = self._textarea.textCursor()
        for r in records:
            if r.get_status() >= Record.Status.TextLoaded:
                if r.text != "":
                    appendix = "\n\n" if \
                            not tc.hasSelection() \
                            and tc.position() == len(self._textarea.toPlainText()) \
                        else ""
                    text = r.text + appendix

                    had_selection = tc.hasSelection()
                    old_selection_start_pos = tc.selectionStart()

                    tc.insertText(text)

                    if had_selection:
                        tc.setPosition(old_selection_start_pos)
                        tc.movePosition(QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor, len(text))  # doesn't work...
                        # tc.setPosition(old_selection_start_pos + len(text), QtGui.QTextCursor.MoveMode.KeepAnchor)

                r.set_status(Record.Status.TextInserted)
                self._textarea.setFocus()
            else:
                # raise Exception  # TODO ?
                print(f"{repr(self)}'s text is not loaded. (Current status = {self._status})")

    def _set_records_list_visibility(self, state: bool) -> None:
        if state != config.options["records_list_shown"]:
            config.options["records_list_shown"] = state
            self.save_config_delayed()
        self._records_list_widget.setVisible(state)

    def _copy_textarea_text(self) -> None:
        print("hello")
        text = self._textarea.textCursor().selectedText()
        cb = QtWidgets.qApp.clipboard()
        if cb is not None:
            cb.setText(text)

    def apply_always_prevent_sleep_mode(self) -> None:
        if config.options["do_prevent_from_sleep_all_the_time"]:
            prevent_sleep.set_prevent_sleep_mode(True)
        else:
            if not self._states & States.Recording:
                prevent_sleep.set_prevent_sleep_mode(False)






