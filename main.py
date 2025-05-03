from PyQt5 import QtCore, QtWidgets, QtGui

import traceback
import os
import sys

import threading

import pyaudio

import numpy as np
import whisper
import torch

import config

from resources import get_resource_path, set_bundle_dir_by_main_file
set_bundle_dir_by_main_file(__file__)

CHUNK = 16
FORMAT = pyaudio.paInt16
CHANNELS = 1  # if sys.platform == 'darwin' else 2  # 2 channels are encoded differently, so whisper.transcribe() doesn't understand anything
RATE = 16000


model = None

def load_model(path: str):
    global model
    model = whisper.load_model(path, in_memory=True)
    return model


def recognize(audio_data):
    global model
    audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)  / 32768.0
    result = model.transcribe(audio_np, fp16=torch.cuda.is_available())
    text = result['text'].strip()
    return text


def record(interrupt_check_function, stopped_callback):
    p = pyaudio.PyAudio()

    audio_data = [bytes()]

    def callback(in_data, frame_count, time_info, status):
        audio_data[0] += in_data
        if interrupt_check_function():
            status = pyaudio.paAbort
            stopped_callback(audio_data[0])
            stream.close()
            p.terminate()
        else:
            status = pyaudio.paContinue
        return (None, status)

    stream = p.open(
        format=FORMAT, channels=CHANNELS, rate=RATE,
        input=True,
        stream_callback=callback
    )



ICON_LOADING = get_resource_path("icons/loading.svg")
ICON_START = get_resource_path("icons/start.svg")
ICON_STOP = get_resource_path("icons/stop.svg")
ICON_RECORDING = get_resource_path("icons/recording.svg")
ICON_ANALYZING = get_resource_path("icons/analyzing.svg")
ICON_APP = get_resource_path("icons/app.svg")
ICON_SETTINGS = get_resource_path("icons/settings.svg")


class States:
    Loading = 1
    Idle = 2
    Recording = 3
    Recognizing = 4


def get_state_icon(state: int):
    if state == States.Loading:
        return QtGui.QIcon(ICON_LOADING)
    elif state == States.Idle:
        return QtGui.QIcon(ICON_START)
    elif state == States.Recording:
        return QtGui.QIcon(ICON_RECORDING)
    elif state == States.Recognizing:
        return QtGui.QIcon(ICON_ANALYZING)
    else:
        raise Exception(f"Unknown state: {state}")



class MicButton(QtWidgets.QPushButton):
    state_changed = QtCore.pyqtSignal(int)

    def __init__(self):
        super().__init__()

    def set_state(self, state: int) -> None:
        self.setIcon(get_state_icon(state))
        self.state_changed.emit(state)


class SettingsWindow(QtWidgets.QWidget):
    always_on_top_changed = QtCore.pyqtSignal()
    config_changed = QtCore.pyqtSignal()
    model_path_changed = QtCore.pyqtSignal()

    def __init__(self, parent = None):
        super().__init__(parent)
        self.resize(400, 200)

        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(QtCore.Qt.WindowType.Window, True)
        self.setWindowTitle(f"Settings - {config.PROGRAM_NAME}")
        self.setWindowIcon(QtGui.QIcon(ICON_APP))

        self._le_model_path = QtWidgets.QLineEdit(config.options["model_path"])
        self._le_model_path.setReadOnly(True)

        self._btn_model_path = QtWidgets.QPushButton("Select...")
        self._btn_model_path.clicked.connect(self._select_model_path)

        self._cb_always_on_top = QtWidgets.QCheckBox("Show window always on top")
        self._cb_always_on_top.setChecked(config.options["window_stays_on_top"])
        self._cb_always_on_top.stateChanged.connect(self._always_on_top_changed)

        self._cb_remember_size = QtWidgets.QCheckBox("Remember window size")
        self._cb_remember_size.setChecked(config.options["remember_window_size"])
        self._cb_remember_size.stateChanged.connect(self._remember_size_changed)

        self._cb_remember_pos = QtWidgets.QCheckBox("Remember window position")
        self._cb_remember_pos.setChecked(config.options["remember_window_pos"])
        self._cb_remember_pos.stateChanged.connect(self._remember_pos_changed)

        self._layout = QtWidgets.QGridLayout()
        self._layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(QtWidgets.QLabel("Path to whisper model file:"), 0, 0, 1, 2)
        self._layout.addWidget(self._le_model_path, 1, 0, 1, 1)
        self._layout.addWidget(self._btn_model_path, 1, 1, 1, 1)
        self._layout.addWidget(self._cb_always_on_top, 2, 0, 1, 2)
        self._layout.addWidget(self._cb_remember_pos, 3, 0, 1, 2)
        self._layout.addWidget(self._cb_remember_size, 4, 0, 1, 2)
        self.setLayout(self._layout)

    def _always_on_top_changed(self, state: bool) -> None:
        state = bool(state)
        config.options["window_stays_on_top"] = state
        self.config_changed.emit()
        self.always_on_top_changed.emit()
        self.show()

    def _remember_size_changed(self, state: bool) -> None:
        state = bool(state)
        config.options["remember_window_size"] = state
        self.config_changed.emit()

    def _remember_pos_changed(self, state: bool) -> None:
        state = bool(state)
        config.options["remember_window_pos"] = state
        self.config_changed.emit()

    def _select_model_path(self) -> None:
        path, f = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select whisper model file",
            None,
            None,
            None,
        )
        config.options["model_path"] = path
        self._le_model_path.setText(path)
        self.config_changed.emit()
        self.model_path_changed.emit()


class MainWindow(QtWidgets.QWidget):
    recording_stopped = QtCore.pyqtSignal(bytes)
    error_occured = QtCore.pyqtSignal(str, str)
    text_insertion_event = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.PROGRAM_NAME)
        self.resize(400, 300)

        self._btn_recording = MicButton()
        self._btn_recording.clicked.connect(self._recording_pressed)
        self._btn_recording.setIconSize(QtCore.QSize(64, 64))
        self._btn_recording.setFixedSize(70, 70)
        self._btn_recording.state_changed.connect(self._btn_state_changed)

        self._label_status = QtWidgets.QLabel()
        self._label_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft)

        self._btn_settings = QtWidgets.QPushButton(QtGui.QIcon(ICON_SETTINGS), "")
        self._btn_settings.setToolTip("Settings...")
        self._btn_settings.setFixedSize(24, 24)
        self._btn_settings.clicked.connect(self._show_settings)

        self._textarea = QtWidgets.QPlainTextEdit()
        self._textarea.setStyleSheet("font-family: 'Liberation Mono', 'Consolas', monospace;")

        self._layout = QtWidgets.QGridLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(self._btn_recording, 0, 0, 1, 1)
        self._layout.addWidget(self._label_status, 0, 1, 1, 1)
        self._layout.addWidget(self._btn_settings, 0, 2, 1, 1, QtCore.Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(self._textarea, 1, 0, 1, 3)

        self._config_window = SettingsWindow(self)

        self._stop_request: bool = False
        self._is_recording = False
        self._is_recognizing = False
        self._config_saving_timer = -1
        self._window_moving_timer = -1

        self.recording_stopped.connect(self._recording_stopped)
        self.error_occured.connect(self._error_occured)
        self.text_insertion_event.connect(self._textarea.textCursor().insertText)

        self.set_stays_on_top()

        self._config_window.always_on_top_changed.connect(self.set_stays_on_top)
        self._config_window.config_changed.connect(lambda: config.save())
        self._config_window.model_path_changed.connect(self._load_model)

    def _load_model(self):
        def f():
            self._label_status.setText("Loading the model...")
            self._btn_recording.set_state(States.Loading)
            try:
                if config.options["model_path"] == "":
                    raise Exception("Path to model file is empty")
                if not os.path.isfile(config.options["model_path"]):
                    raise Exception("Path to model does not point to a file")
                load_model(config.options["model_path"])
            except Exception as e:
                self.error_occured.emit(
                    "Error while loading the model",
                    traceback.format_exc(),
                )
                self._label_status.setText("Error while loading the model.")
                return
            self._btn_recording.set_state(States.Idle)
            self._label_status.setText("Model loaded. Ready to record.")

        thread_load_model = threading.Thread(
            target=f,
        )
        thread_load_model.start()


    def _recording_pressed(self):
        global model
        if model is None:
            return
        if self._is_recognizing:
            return
        if not self._is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        def check_for_stop():
            return self._stop_request

        def rec():
            record(check_for_stop, self.recording_stopped.emit)

        thread_record = threading.Thread(
            target=rec
        )
        thread_record.start()

        self._label_status.setText("Recording...")
        self._btn_recording.set_state(States.Recording)
        self._is_recording = True

    def _stop_recording(self):
        self._stop_request = True
        self._label_status.setText("Stopping recording...")

    def _recording_stopped(self, audio_data):
        def f():
            self._is_recognizing = True
            text = recognize(audio_data) + "\n"
            self.text_insertion_event.emit(text)
            self._btn_recording.set_state(States.Idle)
            self._label_status.setText("Ready to record.")
            self._is_recognizing = False

        self._stop_request = False
        self._is_recording = False

        self._btn_recording.set_state(States.Recognizing)
        self._label_status.setText("Recognizing audio...")

        t_recognize = threading.Thread(
            target=f
        )
        t_recognize.start()

    def _error_occured(self, title, msg: str):
        QtWidgets.QMessageBox.critical(
            self,
            title,
            f"<pre>{msg}</pre>",
        )

    def _btn_state_changed(self, state: int):
        if state == States.Recording:
            QtWidgets.qApp.setWindowIcon(get_state_icon(state))
        else:
            QtWidgets.qApp.setWindowIcon(QtGui.QIcon(ICON_APP))

    def set_stays_on_top(self) -> None:
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, config.options["window_stays_on_top"])
        self.show()

    def remember_geometry(self) -> None:
        x, y = self.x(), self.y()
        w, h = self.width(), self.height()
        config.options["window_geometry"] = [x, y, w, h]
        if config.options["remember_window_pos"] or config.options["remember_window_size"]:
            config.save()

    def moveEvent(self, a0):
        self._window_moving_timer = self.startTimer(2000)
        return super().moveEvent(a0)

    def resizeEvent(self, a0):
        self._window_moving_timer = self.startTimer(2000)
        return super().resizeEvent(a0)

    def save_config_delayed(self) -> None:
        self._config_saving_timer = self.startTimer(1000)

    def timerEvent(self, event: QtCore.QTimerEvent):
        if event.timerId() == self._config_saving_timer:
            config.save()
            self.killTimer(self._config_saving_timer)

        if event.timerId() == self._window_moving_timer:
            self.remember_geometry()
            self.killTimer(self._window_moving_timer)

        return super().timerEvent(event)

    def restore_geometry_from_config(self) -> None:
        x, y, w, h = config.options["window_geometry"]
        if config.options["remember_window_size"] and w != 0 and h != 0:
            self.resize(w, h)
        if config.options["remember_window_pos"] and x != 0 and y != 0:
            s = QtWidgets.qApp.screenAt(QtCore.QPoint(x, y))
            if not s is None:
                self.move(x, y)

    def closeEvent(self, a0):
        config.save()
        return super().closeEvent(a0)

    def _show_settings(self) -> None:
        self._config_window.show()
        self._config_window.move(
            int(self.x() + self.width()/2 - self._config_window.width()/2),
            int(self.y() + self.height()/2 - self._config_window.height()/2),
        )



app = QtWidgets.QApplication([])
app.setWindowIcon(QtGui.QIcon(ICON_APP))

window = MainWindow()
window.show()
window.restore_geometry_from_config()

window._load_model()

app.exec()

