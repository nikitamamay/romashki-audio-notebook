import typing

from PyQt5 import QtCore, QtWidgets, QtGui

import traceback
import os
import sys
import math

import threading

from . import audio
from . import record
from .record import Record


class AudioVisualizerWidget(QtWidgets.QWidget):
    MAX_FPS = 30

    SCALE = 20
    """ Amount of pixels which one second of recording takes. """

    def __init__(self, parent = None) -> None:
        super().__init__(parent)
        self._record: Record | None = None

        # self._data: list[float] = []
        self._last_audio_data_byte_index: int = 0
        self._audio_visualization_data: list[float] = []
        """
        Contains relative heights of audio bars. Each audio bar is one pixel wide.
        """

        self.setMinimumSize(30, 100)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(1000 // self.MAX_FPS)
        self._timer.timeout.connect(self._check_for_redraw)
        self._timer.start()

        # self.setAutoFillBackground(False)  # TODO

    #     self._thread_data_updater = threading.Thread(
    #         target=self._update_data,
    #     )

    # def __del__(self) -> None:
    #     self._thread_data_updater.join()

    def paintEvent(self, event: QtGui.QPaintEvent | None) -> None:
        painter = QtGui.QPainter(self)

        # painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

        half_height = int((self.height()) / 2)

        # painter.setPen(QtWidgets.qApp.palette().color(QtGui.QPalette.ColorRole.Dark))
        # painter.drawLine(QtCore.QPoint(0, half_height), QtCore.QPoint(self.width(), half_height))

        painter.setPen(QtWidgets.qApp.palette().color(QtGui.QPalette.ColorRole.WindowText))

        bar_max_height: float = half_height

        avd_len = len(self._audio_visualization_data)
        w = self.width()
        x = 0
        i = max(avd_len - w, 0)
        while i < avd_len and x < w:
            mx = self._audio_visualization_data[i]
            dy = int(mx * bar_max_height)
            painter.drawLine(QtCore.QPoint(x, half_height - dy), QtCore.QPoint(x, half_height + dy))
            x += 1
            i += 1

    def _update_data(self) -> int:
        """
        Returns count of new audio bars appended.
        """
        if self._record is not None:
            old_byte_index = self._last_audio_data_byte_index

            values_count_in_one_bar_width = int(self._record.audio_params.rate / self.SCALE)
            bars_count = len(self._record.audio_data[old_byte_index : ]) // values_count_in_one_bar_width // self._record.audio_params.get_byte_count()

            if bars_count <= 0:
                return 0

            self._last_audio_data_byte_index += (values_count_in_one_bar_width * bars_count) * self._record.audio_params.get_byte_count()

            normalized_values: list[float] = list(self._record.audio_params.normalize_audio(self._record.audio_data[old_byte_index : self._last_audio_data_byte_index]))

            # try:
            i = 0
            for bar_i in range(bars_count):
                mx = 0.0

                while i < (bar_i + 1) * values_count_in_one_bar_width:
                    value = normalized_values[i]
                    mx = mx if value < mx else value
                    i += 1

                self._audio_visualization_data.append(mx)

            return bars_count
            # except:
            #     print(i)
            #     print(len(normalized_values))

        return 0

    def _check_for_redraw(self) -> None:
        bars_count = self._update_data()
        if bars_count > 0:
            self.update()

    def set_record(self, r: Record | None) -> None:
        self._record = r
        self._audio_visualization_data.clear()
        self._last_audio_data_byte_index = 0
        self._update_data()
        self.update()
        if self._record is None:
            self._timer.stop()
        else:
            self._timer.start()


if __name__ == "__main__":

    app = QtWidgets.QApplication([])

    r = Record.from_file("D:/programms/Python/2025/romashki-audio-notebook/test3-whispercpp/2026.05.03-13.35.16.wav")

    norm = list(r.audio_params.normalize_audio(r.audio_data))
    print(len(r.audio_data), len(norm))

    w = AudioVisualizerWidget()
    w.resize(400, 300)

    w.set_record(r)

    w.show()

    app.exec()