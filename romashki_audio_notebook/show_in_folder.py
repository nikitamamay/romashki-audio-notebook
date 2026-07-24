import typing

import os
import sys


def open_folder(path: str) -> None:
    raise Exception(f"Not implemented for platform '{sys.platform}'")

def show_in_folder(files: list[str]) -> None:
    raise Exception(f"Not implemented for platform '{sys.platform}'")


if sys.platform == "win32":

    def _escape_path_win32(f: str) -> str:
        return f.replace("\"", "\\\"")

    def open_folder(path: str) -> None:
        os.system(f"explorer.exe \"{_escape_path_win32(path)}\"")

    def show_in_folder(files: list[str]) -> None:
        s_select = ""
        for filepath in files:
            filepath = os.path.normpath(filepath)
            s_select += f" /select,\"{_escape_path_win32(filepath)}\""
        os.system(f"explorer.exe {s_select}")


elif sys.platform == "linux":
    def _escape_path_linux(f: str) -> str:
        return f.replace("\"", "\\\"")

    def open_folder(path: str) -> None:
        os.system(f"xdg-open \"{_escape_path_linux(path)}\"")

    def show_in_folder(files: list[str]) -> None:
        if len(files) == 0:
            return

        arr_str = []
        for filepath in files:
            filepath = os.path.normpath(filepath)
            arr_str.append(f"\"{_escape_path_linux(filepath)}\"")

        os.system(f'dbus-send --session --dest=org.freedesktop.FileManager1 --type=method_call /org/freedesktop/FileManager1 org.freedesktop.FileManager1.ShowItems array:string:{",".join(arr_str)} string:""')


