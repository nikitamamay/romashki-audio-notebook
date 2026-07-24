import sys


def set_prevent_sleep_mode(state: bool) -> None:
    pass



if sys.platform == "win32":
    import ctypes

    # Windows API constants
    ES_CONTINUOUS = 0x80000000
    ES_DISPLAY_REQUIRED = 0x00000002
    ES_SYSTEM_REQUIRED = 0x00000001

    def set_prevent_sleep_mode(state: bool) -> None:
        if state:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


elif sys.platform == "linux":
    print(f"prevent_sleep.py: Warning: Untested for Linux")

    try:
        import dbus  # pip install dbus-python
    except:
        print("prevent_sleep.py: Error: cannot import `dbus` module")
        dbus = None

    if dbus is not None:
        class __lsp():
            """ Linux Sleep Preventer object --- singleton """
            session_bus = dbus.SessionBus()
            proxy = session_bus.get_object('org.gnome.SessionManager', '/org/gnome/SessionManager')
            interface = dbus.Interface(proxy, 'org.gnome.SessionManager')
            cookie = None

        def set_prevent_sleep_mode(state: bool) -> None:
            if state:
                if __lsp.cookie is None:
                    __lsp.cookie = __lsp.interface.Inhibit(
                        'YourAppName',
                        dbus.ObjectPath('/'),
                        'Reason for activity',
                        8  # Inhibit flags: screensaver + sleep
                    )
            else:
                if __lsp.cookie is not None:
                    __lsp.interface.Uninhibit(__lsp.cookie)
                    __lsp.cookie = None

else:
    raise Exception(f"Unsupported platform '{sys.platform}'")