import typing

from . import config_reader


PROGRAM_NAME = "Romashki Audio Notebook"
APP_CONFIG_FOLDER = config_reader.get_user_config_folder(PROGRAM_NAME)



cr = config_reader.ConfigReader.load_or_create_default_config_in_configfolder(
    APP_CONFIG_FOLDER,
    {
        # see default options below in CONFIG CHECK section
    }
)
cr._verbose_saving = True

save = cr.save
options = cr._cfg

# print("Config loaded:", options)


### CONFIG CHECK

def _check(b: typing.Any) -> None:
    if not bool(b): raise Exception()

def check():
    try:
        _check(isinstance(options["window_stays_on_top"], bool))
    except:
        options["window_stays_on_top"] = True

    try:
        _check(isinstance(options["remember_window_size"], bool))
    except:
        options["remember_window_size"] = False

    try:
        _check(isinstance(options["remember_window_pos"], bool))
    except:
        options["remember_window_pos"] = False

    try:
        _check(isinstance(options["window_geometry"], list))
        _check(len(options["window_geometry"]) == 4)
        for el in options["window_geometry"]:
            _check(isinstance(el, int) and el > 0)
    except:
        options["window_geometry"] = [0, 0, 400, 300]

    try:
        _check(isinstance(options["do_minimize_to_tray_on_close"], bool))
    except:
        options["do_minimize_to_tray_on_close"] = True

    try:
        _check(isinstance(options["whisper_executable_path"], str))
    except:
        options["whisper_executable_path"] = ""

    try:
        _check(isinstance(options["whisper_model_path"], str))
    except:
        options["whisper_model_path"] = ""

    try:
        _check(isinstance(options["whisper_language"], str))
    except:
        options["whisper_language"] = "auto"

    try:
        _check(isinstance(options["records_dir_path"], str))
    except:
        options["records_dir_path"] = ""

    try:
        _check(isinstance(options["do_remove_records_on_exit"], bool))
    except:
        options["do_remove_records_on_exit"] = False

    try:
        _check(isinstance(options["records_list_shown"], bool))
    except:
        options["records_list_shown"] = True

    try:
        _check(isinstance(options["do_prevent_from_sleep_all_the_time"], bool))
    except:
        options["do_prevent_from_sleep_all_the_time"] = False



check()
