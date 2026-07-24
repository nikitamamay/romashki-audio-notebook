import typing

import os
import sys
import math

import subprocess

import wave
import struct

import datetime

import traceback


class AudioFormat(int):
    """
    Audio formats supported by pulseaudio's pacat.

    Usually default format is `s16le`.

    See https://www.freedesktop.org/wiki/Software/PulseAudio/Documentation/User/SupportedAudioFormats/
    """

    u8 = 1
    """unsigned 8-bit integer"""
    s16le = 4
    """signed 16-bit little-endian integer"""
    s16be = 5
    """signed 16-bit big-endian integer"""
    float32le = 6
    """32-bit little-endian float"""
    float32be = 7
    """32-bit big-endian float"""
    s32le = 8
    """signed 32-bit little-endian integer"""
    s32be = 9
    """signed 32-bit big-endian integer"""
    s24le = 10
    """signed 24-bit little-endian integer (note: ALSA calls this "S24_3LE")"""
    s24be = 11
    """signed 24-bit big-endian integer (note: ALSA calls this "S24_3BE")"""
    s24_32le = 12
    """signed 24-bit little-endian integer, packed into a 32-bit integer so that the 8 most significant bits are ignored (note: ALSA calls this "S24_LE")"""
    s24_32be = 13
    """signed 24-bit big-endian integer, packed into a 32-bit integer so that the 8 most significant bits are ignored (note: ALSA calls this "S24_BE")"""


class AudioParameters():
    """

    Usually default format is `s16le`.
    """
    def __init__(
            self,
            fmt: int = AudioFormat.s16le,
            rate: int = 16000,
            chunk_size: int = 128, # 2, # 16,  # 256
            channels: int = 1,  # 2,
            ) -> None:
        self.format: int = fmt
        self.channels: int = channels
        self.rate: int = rate
        self.chunk_size: int = max(chunk_size, self.get_byte_count())
        """ count of bytes for single chunk """

    def get_pacat_format(self):
        return {
            AudioFormat.u8: "u8",
            AudioFormat.s16le: "s16le",
            AudioFormat.s16be: "s16be",
            AudioFormat.float32le: "float32le",
            AudioFormat.float32be: "float32be",
            AudioFormat.s32le: "s32le",
            AudioFormat.s32be: "s32be",
            AudioFormat.s24le: "s24le",
            AudioFormat.s24be: "s24be",
            AudioFormat.s24_32le: "s24-32le",
            AudioFormat.s24_32be: "s24-32be",
        }[self.format]

    def get_pyaudio_format(self):
        import pyaudio
        return {
            AudioFormat.u8: pyaudio.paUInt8,
            AudioFormat.s16le: pyaudio.paInt16,
            AudioFormat.s16be: pyaudio.paInt16,
            AudioFormat.float32le: pyaudio.paFloat32,
            AudioFormat.float32be: pyaudio.paFloat32,
            AudioFormat.s32le: pyaudio.paInt32,
            AudioFormat.s32be: pyaudio.paInt32,
            AudioFormat.s24le: pyaudio.paInt24,
            AudioFormat.s24be: pyaudio.paInt24,
            # AudioFormat.s24_32le: 0,
            # AudioFormat.s24_32be: 0,
        }[self.format]

    def get_byte_count(self):
        if self.format in (
            AudioFormat.u8,
        ): return 1

        if self.format in (
            AudioFormat.s16le,
            AudioFormat.s16be,
        ): return 2

        if self.format in (
            AudioFormat.s24le,
            AudioFormat.s24be,
        ): return 3

        if self.format in (
            AudioFormat.float32le,
            AudioFormat.float32be,
            AudioFormat.s32le,
            AudioFormat.s32be,
            AudioFormat.s24_32le,
            AudioFormat.s24_32be,
        ): return 4

        raise Exception(f"Unknown format '{self.format}'")

    def get_endian(self) -> typing.Literal["little"] | typing.Literal["big"]:
        return "big" if "be" in self.get_pacat_format() else "little"

    def get_frame_normalize_function(self) -> typing.Callable[[bytes], float]:
        plain_formats_int = {
            AudioFormat.u8: ("B", 0xff),
            AudioFormat.s16le: ("<h", 0xffff  // 2),
            AudioFormat.s16be: (">h", 0xffff  // 2),
            AudioFormat.s32le: (">i", 0xffffffff  // 2),
            AudioFormat.s32be: ("<i", 0xffffffff  // 2),
            AudioFormat.s24_32le: ("<i", 0xffffff  // 2),
            AudioFormat.s24_32be: (">i", 0xffffff  // 2),
        }
        formats_24_32 = {
            AudioFormat.s24le: (">ccc", 0xffffff  // 2),
            AudioFormat.s24be: ("<ccc", 0xffffff  // 2),
        }
        plain_formats_float = {
            AudioFormat.float32le: "<f",
            AudioFormat.float32be: ">f",
        }

        if self.format in plain_formats_int:
            f, mx = plain_formats_int[self.format]
            def func(frame: bytes) -> float:
                return struct.unpack(f, frame)[0] / mx
            return func

        if self.format in formats_24_32:
            f, mx = formats_24_32[self.format]
            def func(frame: bytes) -> float:
                return int.from_bytes(frame, self.get_endian(), signed=True) / mx
            return func

        if self.format in plain_formats_float:
            f = plain_formats_float[self.format]
            def func(frame: bytes) -> float:
                return struct.unpack(f, frame)[0]
            return func

        raise Exception(f"Not implemented decoding function for format '{self.format}'")

    def normalize_audio(self, audio_bytes: bytes, is_reversed: bool = False) -> typing.Generator[float, None, None]:
        frame_size = self.get_byte_count()
        norm_func = self.get_frame_normalize_function()

        if (len(audio_bytes) // frame_size * frame_size) != len(audio_bytes):
            raise Exception(f"Bad audio_bytes length={len(audio_bytes)} with frame_size={frame_size}")

        if not is_reversed:
            # for i in range(0, len(audio_bytes) - frame_size + 1, frame_size):
            #     yield norm_func(audio_bytes[i : i + frame_size])

            i = 0
            end = len(audio_bytes) - 1 # frame_size
            while i < end:
                yield norm_func(audio_bytes[i : i + frame_size])
                i += frame_size
        else:
            i = len(audio_bytes) - frame_size - 1
            while i >= 0:
                yield norm_func(audio_bytes[i : i + frame_size])
                i -= frame_size

    def get_duration(self, bytes_count: int) -> float:
        return bytes_count / self.get_byte_count() / self.rate


# def rms(audio_np: np.ndarray) -> float:
#     s = 0.0
#     for i, num in enumerate(audio_np):
#         s += num ** 2
#     return math.sqrt(s / i)


# def rms_to_db(rms: float) -> float:
#     return math.log(rms) / 2





def switch_endian(a1, a2):
    raise Exception("Not implemented")


def write_wav(
        file: str | typing.IO[bytes],
        data: bytes,
        audio_params: AudioParameters,
        ) -> None:
    if audio_params.get_endian() == "big":
        data_to_write = switch_endian(data, audio_params.get_byte_count())
    else:
        data_to_write = data

    with wave.Wave_write(file) as f:
        f.setnchannels(audio_params.channels)
        f.setsampwidth(audio_params.get_byte_count())
        f.setframerate(audio_params.rate)
        f.writeframesraw(data_to_write)


def load_wav(
        file: str | typing.IO[bytes],
        ) -> tuple[bytes, AudioParameters]:
    audio_params = AudioParameters()
    with wave.Wave_read(file) as f:
        audio_params.channels = f.getnchannels()
        # audio_params.format = lalala if f.getsampwidth()
        audio_params.rate = f.getframerate()
        print(f.getparams())
        data = f.readframes(f.getnframes())
    return data, audio_params


### PLATFORM-SPECIFIC


class CallbackRecorder:
    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        raise Exception(f"Not implemented")

    def get_stderr(self) -> str:
        return ""


def record(
        record_time_seconds: float,
        audio_params: AudioParameters,
        ) -> bytes:
    raise Exception(f"Not implemented for platform '{sys.platform}'")

def record_with_callback(
        func_has_stop_request: typing.Callable[[], bool],
        func_data: typing.Callable[[bytes], None],
        func_start: typing.Callable[[], None],
        func_exit: typing.Callable[[int], None],
        audio_params: AudioParameters,
        ) -> CallbackRecorder:
    raise Exception(f"Not implemented for platform '{sys.platform}'")

def playback(
        data: bytes,
        audio_params: AudioParameters,
        ) -> None:
    raise Exception(f"Not implemented for platform '{sys.platform}'")


# if sys.platform == "win32":
if True:
    import pyaudio

    _py_audio = pyaudio.PyAudio()

    class CallbackRecorderPyAudio(CallbackRecorder):
        def __init__(self, stream: pyaudio.Stream) -> None:
            super().__init__()
            self._stream: pyaudio.Stream = stream

        def close(self) -> None:
            # self._stream.close()
            self._stream.stop_stream()

    def record_with_callback(
            func_has_stop_request: typing.Callable[[], bool],
            func_data: typing.Callable[[bytes], None],
            func_start: typing.Callable[[], None],
            func_exit: typing.Callable[[int], None],
            audio_params: AudioParameters,
            ) -> CallbackRecorder:

        data = [bytes(), False]
        """ `[ audio_data: bytes, is_started: bool ]` """

        def callback(in_data, frame_count, time_info, status):
            if not data[1]:
                data[1] = True
                func_start()

            if in_data is not None:
                func_data(in_data)

            if func_has_stop_request(): # or status in (pyaudio.paCal): # TODO
                status = pyaudio.paAbort
                stream.close()
                func_exit(0)
                # __py_audio.terminate()
            else:
                status = pyaudio.paContinue
            return (None, status)

        # see pyaudio.PyAudio.Stream
        stream = _py_audio.open(
            format=audio_params.get_pyaudio_format(),
            channels=audio_params.channels,
            rate=audio_params.rate,
            frames_per_buffer=audio_params.chunk_size // audio_params.get_byte_count(),
            input=True,
            stream_callback=callback,
        )

        return CallbackRecorderPyAudio(stream)

    def record(
            record_time_seconds: float,
            audio_params: AudioParameters,
            ) -> bytes:
        stream = _py_audio.open(
            format=audio_params.get_pyaudio_format(),
            channels=audio_params.channels,
            rate=audio_params.rate,
            input=True,
        )
        return stream.read(int(record_time_seconds * audio_params.rate))


    def playback(
            data: bytes,
            audio_params: AudioParameters,
            ) -> None:
        stream = _py_audio.open(
            format=audio_params.get_pyaudio_format(),
            channels=audio_params.channels,
            rate=audio_params.rate,
            output=True,
        )
        stream.write(data)



elif sys.platform == "linux":
    import subprocess
    import threading
    # import multiprocessing  # threading is not suitable, because of global interpreter lock

    class CallbackRecorderLinux(CallbackRecorder):
        def __init__(self) -> None:
            super().__init__()
            self.popen: subprocess.Popen[bytes]|None = None
            self.thread: threading.Thread|None = None
            # self.process: multiprocessing.Process|None = None

        def close(self) -> None:
            if self.popen is not None:
                self.popen.kill()
            self.join_thread()

        def join_thread(self) -> None:
            # if self.process is not None:
            #     # self.process.join()
            #     self.process.kill()

            if self.thread is not None:
                self.thread.join()

        def get_stderr(self) -> str:
            if self.popen is not None:
                if self.popen.stderr is not None:
                    try:
                        b = self.popen.stderr.read()
                        try:
                            return b.decode(errors="ignore")
                        except:
                            print("CallbackRecorderLinux.get_stderr(): Error: Cannot decode stderr")
                            return repr(b)
                    except:
                        print("CallbackRecorderLinux.get_stderr(): Error: Cannot read stderr")
            return ""


    def record_with_callback(
            func_has_stop_request: typing.Callable[[], bool],
            func_data: typing.Callable[[bytes], None],
            func_start: typing.Callable[[], None],
            func_exit: typing.Callable[[int], None],
            audio_params: AudioParameters,
            ) -> CallbackRecorder:
        cr = CallbackRecorderLinux()

        def _th_f():
            try:
                cmd = f"pacat --record --raw --rate={audio_params.rate} --channels={audio_params.channels} --format={audio_params.get_pacat_format()}"

                cr.popen = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=audio_params.chunk_size,
                )

                if cr.popen.stdout is None:
                    raise Exception("stdout is None")

                # started = False

                func_start()

                while True:
                    if func_has_stop_request():
                        cr.popen.send_signal(15)  # SIGTERM
                        # p.kill()
                        # cr.popen.stdout.flush()
                        # func_data(cr.popen.stdout.read())
                    #     rc = 123123
                    # else:
                    #     rc = None

                    # rc = cr.popen.poll()
                    # if rc is None:
                        # if not started:
                        #     func_start()
                        #     started = True
                    cr.popen.stdout.flush()
                    func_data(cr.popen.stdout.read(audio_params.chunk_size))

                    # else:
                    rc = cr.popen.poll()
                    if rc is not None:
                        print(f"Popen for pacat stopped with rc={rc}")
                        func_exit(rc)
                        break

            except Exception as e:
                print(traceback.format_exc())
                func_exit(1)

        # cr.process = multiprocessing.Process(
        #     target=_th_f
        # )
        # cr.process.start()

        cr.thread = threading.Thread(
            target=_th_f,
        )
        cr.thread.start()

        return cr


    def record(
            record_time_seconds: float,
            audio_params: AudioParameters,
            ) -> bytes:
        data = bytes()
        chunks_count = record_time_seconds * audio_params.rate * audio_params.get_byte_count() / audio_params.chunk_size

        cmd = f"pacat --record --raw --rate={audio_params.rate} --channels={audio_params.channels} --format={audio_params.get_pacat_format()}"

        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
        )
        if p.stdout is None:
            raise Exception("stdout is None")

        i = 0
        while i < chunks_count:
            data += p.stdout.read(audio_params.chunk_size)
            i += 1

        p.kill()
        return data


    def playback(
            data: bytes,
            audio_params: AudioParameters,
            ) -> None:
        try:
            cmd = f"pacat --playback --raw --rate={audio_params.rate} --channels={audio_params.channels} --format={audio_params.get_pacat_format()}"

            p = subprocess.Popen(
                cmd,
                shell=True,
                stdin=subprocess.PIPE,
            )
            if p.stdin is None:
                raise Exception("stdout is None")

            p.stdin.write(data)
            p.stdin.close()

            p.wait()

        except Exception as e:
            print(traceback.format_exc())



else:
    raise Exception(f"Unsupported platform '{sys.platform}'")




if __name__ == "__main__":

    def main():

        # ap = AudioParameters(AudioFormat.u8, 16000)
        # ap = AudioParameters(AudioFormat.s16le, 16000, 128, 1)
        # ap = AudioParameters(AudioFormat.float32le, 192000, 128, 1)
        ap = AudioParameters()

        print("start")

        do_stop = False
        audio_data = [bytes()]

        def on_data(d):
            print(f"got data len={len(d)} ({ap.get_duration(len(d))} seconds)")
            audio_data[0] += d

        cr = record_with_callback(
            lambda: do_stop,
            on_data,
            lambda: print("started"),
            lambda rc: print(f"exit. rc={rc}"),
            ap
        )

        from . import progress_printer
        import time

        with progress_printer.ProgressPrinterTime("Recording time:") as pp:
            while True:
                try:
                    pp.print_progress()
                    time.sleep(0.05)

                except KeyboardInterrupt:
                    do_stop = True
                    break

        time.sleep(0.5)

        cr.close()

        data = audio_data[0]

        print(f"Read bytes count: {len(data)} = {ap.get_duration(len(data))} seconds")
        print("playback start")

        write_wav("a.wav", data, ap)
        playback(data, ap)

        print("playback end")
        print("Done")


    main()


    # def main():

    #     # ap = AudioParameters(AudioFormat.u8, 16000)
    #     # ap = AudioParameters(AudioFormat.s16le, 16000, 128, 1)
    #     # ap = AudioParameters(AudioFormat.float32le, 192000, 128, 1)
    #     ap = AudioParameters()

    #     print("start")
    #     data = record(5, ap)

    #     print("Read bytes count:", len(data))
    #     print("playback start")

    #     write_wav("a.wav", data, ap)
    #     playback(data, ap)

    #     print("playback end")

    #     try:
    #         while True:
    #             import time
    #             time.sleep(0.1)
    #             break
    #     except KeyboardInterrupt:
    #         pass

    #     print("Done")


    # main()

