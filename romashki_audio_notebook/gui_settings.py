import typing

from PyQt5 import QtCore, QtWidgets, QtGui

import io
import sys

from .gui_def import *
from . import config





class SettingsWindow(QtWidgets.QWidget):
    always_on_top_changed = QtCore.pyqtSignal()
    config_changed = QtCore.pyqtSignal()

    def __init__(self, parent = None):
        super().__init__(parent)
        self.resize(400, 200)

        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(QtCore.Qt.WindowType.Window, True)
        self.setWindowTitle(f"Settings - {config.PROGRAM_NAME}")
        self.setWindowIcon(QtGui.QIcon(ICON_APP))

        self._le_whisper_exe = QtWidgets.QLineEdit(config.options["whisper_executable_path"])
        self._le_whisper_exe.textEdited.connect(lambda: self._config_str_changed("whisper_executable_path", self._le_whisper_exe.text()))
        set_monospace_font(self._le_whisper_exe.font, self._le_whisper_exe.setFont)

        self._le_whisper_model = QtWidgets.QLineEdit(config.options["whisper_model_path"])
        self._le_whisper_model.textEdited.connect(lambda: self._config_str_changed("whisper_model_path", self._le_whisper_model.text()))
        set_monospace_font(self._le_whisper_model.font, self._le_whisper_model.setFont)

        self._le_whisper_lang = QtWidgets.QLineEdit(config.options["whisper_language"])
        self._le_whisper_lang.textEdited.connect(lambda: self._config_str_changed("whisper_language", self._le_whisper_lang.text()))
        set_monospace_font(self._le_whisper_lang.font, self._le_whisper_lang.setFont)

        self._le_records_dir = QtWidgets.QLineEdit(config.options["records_dir_path"])
        self._le_records_dir.textEdited.connect(lambda: self._config_str_changed("records_dir_path", self._le_records_dir.text()))
        set_monospace_font(self._le_records_dir.font, self._le_records_dir.setFont)

        self._btn_choose_records_dir = QtWidgets.QPushButton("Select...")
        self._btn_choose_records_dir.clicked.connect(self._choose_records_dir)
        self._btn_choose_records_dir.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Maximum)

        self._cb_remove_records_on_exit = QtWidgets.QCheckBox("Remove records from disk on exit")
        self._cb_remove_records_on_exit.setChecked(config.options["do_remove_records_on_exit"])
        self._cb_remove_records_on_exit.stateChanged.connect(lambda state: self._config_boolean_changed("do_remove_records_on_exit", state))

        self._cb_always_on_top = QtWidgets.QCheckBox("Show window always on top")
        self._cb_always_on_top.setChecked(config.options["window_stays_on_top"])
        self._cb_always_on_top.stateChanged.connect(lambda state: self._config_boolean_changed("window_stays_on_top", state))

        self._cb_remember_size = QtWidgets.QCheckBox("Remember window size")
        self._cb_remember_size.setChecked(config.options["remember_window_size"])
        self._cb_remember_size.stateChanged.connect(lambda state: self._config_boolean_changed("remember_window_size", state))

        self._cb_remember_pos = QtWidgets.QCheckBox("Remember window position")
        self._cb_remember_pos.setChecked(config.options["remember_window_pos"])
        self._cb_remember_pos.stateChanged.connect(lambda state: self._config_boolean_changed("remember_window_pos", state))

        self._cb_minimize_to_tray = QtWidgets.QCheckBox("Minimize to tray on window close")
        self._cb_minimize_to_tray.setChecked(config.options["do_minimize_to_tray_on_close"])
        self._cb_minimize_to_tray.stateChanged.connect(lambda state: self._config_boolean_changed("do_minimize_to_tray_on_close", state))

        self._cb_prevent_sleep = QtWidgets.QCheckBox("Always prevent from sleep (not only while recording)")
        self._cb_prevent_sleep.setChecked(config.options["do_prevent_from_sleep_all_the_time"])
        self._cb_prevent_sleep.stateChanged.connect(lambda state: self._config_boolean_changed("do_prevent_from_sleep_all_the_time", state))


        self._layout = QtWidgets.QGridLayout()
        self._layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(QtWidgets.QLabel("Path to whisper-cli executable:"), 0, 0, 1, 1)
        self._layout.addWidget(self._le_whisper_exe, 0, 1, 1, 2)
        self._layout.addWidget(QtWidgets.QLabel("Path to whisper GGML model:"), 1, 0, 1, 1)
        self._layout.addWidget(self._le_whisper_model, 1, 1, 1, 2)
        self._layout.addWidget(QtWidgets.QLabel("Speech language:"), 2, 0, 1, 1)
        self._layout.addWidget(self._le_whisper_lang, 2, 1, 1, 2)
        self._layout.addWidget(QtWidgets.QLabel("Path to records directory:"), 3, 0, 1, 1)
        self._layout.addWidget(self._le_records_dir, 3, 1, 1, 1)
        self._layout.addWidget(self._btn_choose_records_dir, 3, 2, 1, 1)

        self._layout.addWidget(self._cb_remove_records_on_exit, 4, 0, 1, 3)
        self._layout.addWidget(self._cb_always_on_top, 5, 0, 1, 3)
        self._layout.addWidget(self._cb_remember_pos, 6, 0, 1, 3)
        self._layout.addWidget(self._cb_remember_size, 7, 0, 1, 3)
        self._layout.addWidget(self._cb_minimize_to_tray, 8, 0, 1, 3)
        self._layout.addWidget(self._cb_prevent_sleep, 9, 0, 1, 3)
        self.setLayout(self._layout)

    def _config_boolean_changed(self, key: str, state: bool) -> None:
        state = bool(state)
        config.options[key] = state
        self.config_changed.emit()

    def _config_str_changed(self, key: str, value: str) -> None:
        config.options[key] = value.strip()
        self.config_changed.emit()

    def _always_on_top_changed(self, state: bool) -> None:
        self._config_boolean_changed("window_stays_on_top", state)
        self.always_on_top_changed.emit()
        self.show()

    def _choose_records_dir(self) -> None:
        dirpath = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select records directory", config.options["records_dir_path"])
        if dirpath != "":
            self._le_records_dir.setText(dirpath)
            self._config_str_changed("records_dir_path", dirpath)

    # def _show_whisper_cmd_help(self) -> None:
    #     QtWidgets.QMessageBox.information(
    #         self,
    #         "Info for whisper-cli",
    #         """<style>table { border-collapse: collapse } td, th { border: 1px solid #888; padding: 3px }</style>
    #         <p>Set command with arguments or path to shell script which runs <code>whisper-cli</code>:</p>
    #         <table>
    #             <tr>
    #                 <th>state</th>
    #                 <th>description</th>
    #                 <th>arguments example</th>
    #             </tr>
    #             <tr>
    #                 <td>required</td>
    #                 <td>get wave audio using <b>stdin</b></td>
    #                 <td><code>-f -</code></td>
    #             </tr>
    #             <tr>
    #                 <td>required</td>
    #                 <td>outputs in txt format</td>
    #                 <td><code>--output-txt</code></td>
    #             </tr>
    #             <tr>
    #                 <td>recommended</td>
    #                 <td>full path to <code>whisper-cli</code> executable</td>
    #                 <td></td>
    #             </tr>
    #             <tr>
    #                 <td>recommended</td>
    #                 <td>uses specified model</td>
    #                 <td><code>-m "/path/to/model"</code></td>
    #             </tr>
    #             <tr>
    #                 <td>recommended</td>
    #                 <td>sets a language</td>
    #                 <td><code>-l ru</code></td>
    #             </tr>
    #             <tr>
    #                 <td>recommended</td>
    #                 <td>sets preferred threads count</td>
    #                 <td><code>-t 4</code></td>
    #             </tr>
    #             <tr>
    #                 <td>recommended</td>
    #                 <td>supresses non-speech output</td>
    #                 <td><code>-sns</code></td>
    #             </tr>
    #         </table>
    #         <p>Example:</p>
    #         <p><code>/opt/whisper.cpp/bin/whisper-cli -m "/home/user/stt_whisper_small_ggml.bin" -l ru --output-txt -sns -t 8 -f -</code></p>
    #         """,
    #     )

