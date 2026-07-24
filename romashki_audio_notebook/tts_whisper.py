import typing
import traceback

import sys
import os

import re

import subprocess

from . import audio

re_spaces_multiple = re.compile(r"\s\s+", re.MULTILINE)


BAD_WHISPER_OUTPUT_PIECES = [
    "Спасибо за просмотр!",
    "С вами был Игорь Негода. До скорого!",
    "Субтитры субтитров Н.Новикова",
    "Субтитры субтитров А.Синецкая",
    "Субтитры субтитров О.Голубки",
    "Корректор А.Егорова",
    "Корректор В.Сухиашвили",
    "Корректор В. Сухиашвили",
    "Редактор субтитров Н.Закомолдина",
    "Редактор субтитров И.Бойкова",
    "Редактор субтитров Т.Горелова",
    "Редактор субтитров А.Семкин",
    "Редактор субтитров Н.Новикова",
    "Редактор субтитров М.Лосева",
    "ПОСМЕИВАЕТСЯ СПОКОЙНАЯ МУЗЫКА",
    "ТАНЦЕВАЛЬНАЯ МУЗЫКА",
    "СПОКОЙНАЯ МУЗЫКА",
]



def replace_ext(filepath: str, new_ext: str) -> str:
    """ `new_ext` must start with dot. """
    return os.path.splitext(filepath)[0] + new_ext


def _escape(text: str) -> str:
    return text \
        .replace("\\", "\\\\") \


def render_file_size(size_bytes: int) -> str:
    """
    Returns file size (`str`) in human-readable format: b, Kb, Mb, Gb.
    """
    if size_bytes > 1073741824:
        return "%.1f GB" % (size_bytes / 1073741824)

    if size_bytes > 1048576:
        return "%.1f MB" % (size_bytes / 1048576)

    if size_bytes > 1024:
        return "%.1f KB" % (size_bytes / 1024)

    return "%i B" % (size_bytes)

# def parse_whispercpp_text(out: str) -> str:
#     result: str = ""
#     for line in out.splitlines(False):
#         line = line.strip()
#         if line == "":
#             continue

#         i1 = line.find("[")
#         i2 = line.find("]", i1)
#         if i1 != -1 and i2 != -1:
#             result += line[i2 + 1:]

#     result = re_spaces_multiple.subn(" ", result)[0]
#     return result


class WhisperCpp():
    def __init__(
            self,
            path_to_executable: str,
            path_to_model: str,
            language: str|None = "auto",
            ) -> None:
        self.threads_count: int|None = None
        self.executable_path: str = path_to_executable
        self.model_path: str = path_to_model
        self.language: str|None = language
        self.do_suppress_non_speech_tokens: bool = True

        # self.processes: list[subprocess.Popen] = []

    def is_valid(self) -> bool:
        return os.path.isfile(self.executable_path)

    def _get_whisper_command(self) -> str:
        cmd = f"\"{self.executable_path}\""
        if self.model_path is not None and self.model_path != "":
            cmd += f" -m \"{_escape(self.model_path)}\""
        if self.language is not None and self.language != "":
            cmd += f" -l \"{self.language}\""
        if self.threads_count is not None and self.threads_count != 0:
            cmd += f" -t \"{self.threads_count}\""
        if self.do_suppress_non_speech_tokens:
            cmd += f" -sns"
        return cmd

    def _execute_whisper(self, cmd: str, do_open_stdin: bool) -> subprocess.Popen:
        if not self.is_valid():
            raise Exception(f"{repr(self)} is not valid")
        print(f"Executing: {cmd}")
        p = subprocess.Popen(
            # executable=self.executable_path,
            args=cmd,
            cwd=os.getcwd(),
            shell=True,
            stdin=subprocess.PIPE if do_open_stdin else None,
            # stdout=subprocess.PIPE,
            stdout=None,
            # stderr=subprocess.PIPE,
            stderr=None,
        )
        # self.processes.append(p)
        return p

    def _get_whisper_output_file_and_format_command(self, output_file_path: str) -> str:
        output_file_path_without_extension, ext = os.path.splitext(output_file_path)
        if ext == ".txt":
            return f" -otxt -of \"{_escape(output_file_path_without_extension)}\""
        elif ext == ".csv":
            return f" -ocsv -of \"{_escape(output_file_path_without_extension)}\""
        elif ext == ".json":
            return f" -ojf -of \"{_escape(output_file_path_without_extension)}\""
        else:
            raise Exception(f"Unsupported output file extension: {repr(ext)}")

    def recognize_file_to_file(
            self,
            audio_file_path: str,
            output_file_path: str,
            ) -> subprocess.Popen:
        cmd = self._get_whisper_command()
        cmd += self._get_whisper_output_file_and_format_command(output_file_path)
        cmd += f" \"{_escape(audio_file_path)}\""  # positional arguments are at the end
        return self._execute_whisper(cmd, False)



def load_txt(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # keeping original output in the file,
    # and post-processing (removing bad pieces) afterwards.
    for bad_piece in BAD_WHISPER_OUTPUT_PIECES:
        text = text.replace(bad_piece, "")

    text, _ = re_spaces_multiple.subn(" ", text.strip())

    return text


# def recognize(
#         whisper_command: str,
#         r: audio.Record,
#         ) -> None:
#     raise Exception(f"Not implemented for platform '{sys.platform}'")




# if sys.platform == "linux":
#     pass
#     # def recognize(
#     #         whisper_command: str,
#     #         r: audio.Record,
#     #         ) -> None:

#     #     p = subprocess.Popen(
#     #         args=whisper_command,
#     #         shell=True,
#     #         stdin=subprocess.PIPE,
#     #         stdout=subprocess.PIPE,
#     #         # stderr=subprocess.PIPE,
#     #         # env=env_for_whisper,
#     #     )
#     #     if p.stdin is None or p.stdout is None:
#     #         raise Exception("stdin or stdout are None")

#     #     # p.stdin.write(r.audio_data)
#     #     audio.write_wav(p.stdin, r.audio_data, r.audio_params)

#     #     p.stdin.close()

#     #     p.wait(300)

#     #     print(f"recognize(): returncode={p.returncode}")

#     #     out = p.stdout.read().decode()
#     #     # out_err = p.stderr.read().decode()

#     #     print(f"recognize(): out={repr(out)}")

#     #     r.text = re_spaces_multiple.subn(" ", out)[0].strip()



# elif sys.platform == "win32":
#     raise Exception("Not implemented")

# else:
#     raise Exception(f"Unsupported platform '{sys.platform}'")
