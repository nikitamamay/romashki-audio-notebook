import typing

import os
import datetime

import subprocess
import threading


from . import audio
from .audio import AudioParameters

from . import tts_whisper
from .tts_whisper import WhisperCpp, replace_ext



def get_default_filename(dirpath: str, ext: str = ".wav") -> str:
    """
    `ext` must start with dot.
    """
    dt = datetime.datetime.now()
    return os.path.join(dirpath, f"{dt.strftime('%Y.%m.%d-%H.%M.%S')}{ext}")



class Record():
    """

    * `record()`
    * `save_wav()`
    * `recognize()`
    * `load_text()`
    """

    class Status:
        JustCreated = 0
        Recording   = 1
        Recorded    = 2
        AudioSaved  = 3
        Recognizing = 4
        Recognized  = 5
        TextLoaded  = 6
        TextInserted     = 7

    def __init__(
            self,
            filename: str,
            audio_params: AudioParameters|None = None
            ) -> None:
        self._status: int = Record.Status.JustCreated

        self.audio_filename: str = filename
        self.audio_data: bytes = bytes()
        self.audio_params: AudioParameters = AudioParameters() if audio_params is None else audio_params
        self.duration: float = 0

        self.text_filename: str = replace_ext(self.audio_filename, ".txt")
        self.text: str = ""

        self.audio_callback_recorder: audio.CallbackRecorder|None = None
        self.whisper_popen: subprocess.Popen|None = None

    @staticmethod
    def from_file(audio_filepath: str, text_filepath: str|None = None) -> 'Record':
        r = Record(audio_filepath)

        if text_filepath is not None:
            r.text_filename = text_filepath

        if os.path.exists(r.audio_filename):
            r.audio_data, r.audio_params = audio.load_wav(r.audio_filename)
            r.duration = len(r.audio_data) / (r.audio_params.rate * r.audio_params.get_byte_count() * r.audio_params.channels)
            if r._status < Record.Status.AudioSaved: r._status = Record.Status.AudioSaved

        if os.path.exists(r.text_filename):
            r.text = tts_whisper.load_txt(r.text_filename)
            r.unset_audio_data()
            if r._status < Record.Status.TextLoaded: r._status = Record.Status.TextLoaded

        return r

    def __del__(self) -> None:
        if self.audio_callback_recorder is not None:
            self.audio_callback_recorder.close()

        if self.whisper_popen is not None:
            self.whisper_popen.kill()

    def set_status(self, status: int) -> None:
        # TODO: make this thread-safe
        self._status = status

    def get_status(self) -> int:
        return self._status

    def format_duration(self) -> str:
        m, s = divmod(int(self.duration), 60)
        return f"{str(m).rjust(2, '0')}:{str(s).rjust(2, '0')}"

    def get_audio_data_size(self) -> int:
        adl = len(self.audio_data)
        if adl > 0:
            return adl
        else:
            return int(self.duration * self.audio_params.rate * self.audio_params.get_byte_count() * self.audio_params.channels)

    def record(
            self,
            func_has_stop_request: typing.Callable[[], bool],
            func_data: typing.Callable[[bytes], None]|None = None,
            func_start: typing.Callable[[], None]|None = None,
            func_exit: typing.Callable[[int], None]|None = None,
            ) -> audio.CallbackRecorder:
        if self._status < Record.Status.JustCreated:
            raise Exception(f"{repr(self)} has bad status. (Current status = {self._status})")

        bytes_in_one_second = self.audio_params.rate * self.audio_params.get_byte_count() * self.audio_params.channels

        if func_data is not None:
            def on_data(chunk: bytes) -> None:
                self.audio_data += chunk
                self.duration += len(chunk) / bytes_in_one_second
                func_data(chunk)
        else:
            def on_data(chunk: bytes) -> None:
                self.duration += len(chunk) / bytes_in_one_second
                self.audio_data += chunk

        def on_start() -> None:
            if self._status < Record.Status.Recording: self._status = Record.Status.Recording
            if func_start is not None:
                func_start()

        def on_exit(rc: int) -> None:
            if self._status < Record.Status.Recorded: self._status = Record.Status.Recorded
            self.duration = len(self.audio_data) / bytes_in_one_second
            if func_exit is not None:
                func_exit(rc)

        self.audio_callback_recorder = audio.record_with_callback(
            func_has_stop_request,
            on_data,
            on_start,
            on_exit,
            self.audio_params,
        )
        return self.audio_callback_recorder

    def save_wav(self) -> None:
        if self._status < Record.Status.Recorded:
            raise Exception(f"{repr(self)} is not recorded. (Current status = {self._status})")
        audio.write_wav(self.audio_filename, self.audio_data, self.audio_params)
        print(f"Record saved to '{self.audio_filename}'")
        self.unset_audio_data()
        if self._status < Record.Status.AudioSaved: self._status = Record.Status.AudioSaved

    def unset_audio_data(self) -> None:
        """ Unload from memory `audio_data` bytes array. """
        self.audio_data = bytes()

    def recognize(
            self,
            whisper_cpp: WhisperCpp,
            on_end_callback: typing.Callable[[int], None]|None,
            ) -> None:  # subprocess.Popen:
        if self._status < Record.Status.AudioSaved:
            raise Exception(f"{repr(self)}'s audio is not saved to disk. (Current status = {self._status})")


        def f():
            self.whisper_popen = whisper_cpp.recognize_file_to_file(self.audio_filename, self.text_filename)
            assert self.whisper_popen is not None
            rc = self.whisper_popen.wait()
            if self._status < Record.Status.Recognized: self._status = Record.Status.Recognized
            if on_end_callback is not None:
                on_end_callback(rc)

        t = threading.Thread(
            target=f
        )
        t.start()
        if self._status < Record.Status.Recognizing: self._status = Record.Status.Recognizing
        # return self.whisper_popen

    def load_text(self) -> None:
        if self._status < Record.Status.Recognized:
            raise Exception(f"{repr(self)} is not recognized. (Current status = {self._status})")

        self.text = tts_whisper.load_txt(self.text_filename)
        print(f"Record's text is loaded from '{self.text_filename}' ({len(self.text)} characters)")
        if self._status < Record.Status.TextLoaded: self._status = Record.Status.TextLoaded



if __name__ == "__main__":
    def main():
        import time

        ap = AudioParameters()

        r = Record(get_default_filename(""), ap)

        time_started = time.time()
        def f_stop() -> bool:
            return time.time() - time_started > 5

        print("recording...")

        r.record(f_stop)

        while r.get_status() < Record.Status.Recorded:
            time.sleep(0.1)

        audio.playback(r.audio_data, ap)

        r.save_wav()

    main()
