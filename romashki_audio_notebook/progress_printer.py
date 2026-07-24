import typing

import time
import sys
import os

PROGRESS_BAR_LENGTH = 30


def get_loading_wheel_char() -> typing.Generator[str, None, None]:
    while True:
        for char in ['/', '-', '\\', '|']:
            yield char

# def loading_wheel(sleep_seconds: float):
#     for char in get_loading_wheel_char():
#         print(char, end="")
#         sys.stdout.flush()

#         time.sleep(sleep_seconds)

#         print("\033[2K\r")

def print_from_start_of_terminal_line(message: str):
    print(f"\033[2K\r{message}", end="")
    sys.stdout.flush()


def render_progress_bar(progress: float) -> str:
    return f"[{('='*round(progress * PROGRESS_BAR_LENGTH)).ljust(PROGRESS_BAR_LENGTH)}]"



class ProgressPrinter():
    """
    Loading wheel progress printer:
    ```
    'Doing something... /'
    ```

    Usage:
    ```
    with ProgressPrinter("Doing something...", 0.5) as pp:
        while True:
            pp.check_for_progress()
            # doing something...
    ```
    """

    def __init__(
            self,
            message: str = "",
            print_interval: float = 0.5,
            ) -> None:
        self.last_measured_time_ns: int = 0
        self.print_interval_ns: int = int(print_interval * 10**9)
        self.message_with_space: str = "" if message == "" else f"{message} "
        self.loading_wheel_char_iter = get_loading_wheel_char()

    def check_time(self) -> bool:
        now = time.time_ns()
        if now - self.last_measured_time_ns > self.print_interval_ns:
            self.last_measured_time_ns = now
            return True
        return False

    def check_for_progress(self) -> None:
        if self.check_time():
            self.print_progress()

    def print_progress(self) -> None:
        print_from_start_of_terminal_line(f"{self.message_with_space}{next(self.loading_wheel_char_iter)}")

    def __enter__(self) -> typing.Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.print_progress()
        print()  # so next line will start correctly from new line
        pass


class ProgressPrinterInteger(ProgressPrinter):
    """
    Integer progress printer:
    ```
    'Iterating... [========                      ]  8 / 30 (26.7%)'
    ```

    Usage:
    ```
    with ProgressPrinterInteger(len(big_list), "Iterating...", 0.5) as pp:
        i = 0
        while i < len(big_list):
            pp.check_for_progress_int(i)

            # doing something...

            i += 1

    ```
    """

    def __init__(
            self,
            total_steps_count: int,
            message: str = "",
            print_interval: float = 0.5,
            ) -> None:
        super().__init__(message, print_interval)

        self.total_steps_count: int = total_steps_count
        self.current_i: int = 0
        self.total_steps_count_str_len = len(str(self.total_steps_count))

    def check_for_progress_int(
            self,
            i: int,
            ) -> None:
        self.current_i = i
        self.check_for_progress()

    def print_progress(self):
        i = self.current_i + 1
        progress = i / self.total_steps_count
        print_from_start_of_terminal_line(
            f"{self.message_with_space}{render_progress_bar(progress)} "
            f"{str(i).rjust(self.total_steps_count_str_len)} "
            f"/ {self.total_steps_count} ({progress*100:.1f}%)"
        )


class ProgressPrinterTime(ProgressPrinter):
    """
    Time measurement printer:
    ```
    'Time spent: 01:23.567'
    ```

    Usage:
    ```
    with ProgressPrinterTime("Time spent:") as pp:
        while True:
            pp.check_for_progress()
            # doing something...
    ```
    """

    def __init__(
            self,
            message: str = "",
            print_interval: float = 0,
            ) -> None:
        super().__init__(message, print_interval)
        self.start_time_ns: int = time.time_ns()

    @staticmethod
    def render_time(time_ns: int) -> str:
        m, s = divmod(time_ns / 1_000_000_000, 60)
        h, m = divmod(m, 60)
        return f"{h:.0f}:{m:02.0f}:{s:06.3f}"

    def print_progress(self):
        print_from_start_of_terminal_line(
            f"{self.message_with_space}{ProgressPrinterTime.render_time(time.time_ns() - self.start_time_ns)}"
        )
