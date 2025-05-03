import config_reader


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

print("Config loaded:", options)


### CONFIG CHECK

def check():
    try:
        assert isinstance(options["window_stays_on_top"], bool)
    except:
        options["window_stays_on_top"] = True

    try:
        assert isinstance(options["remember_window_size"], bool)
    except:
        options["remember_window_size"] = False

    try:
        assert isinstance(options["remember_window_pos"], bool)
    except:
        options["remember_window_pos"] = False

    try:
        assert isinstance(options["window_geometry"], list)
        assert len(options["window_geometry"]) == 4
        for el in options["window_geometry"]:
            assert isinstance(el, int) and el > 0
    except:
        options["window_geometry"] = [0, 0, 400, 300]

    try:
        assert isinstance(options["model_path"], str)
    except:
        options["model_path"] = ""



check()
