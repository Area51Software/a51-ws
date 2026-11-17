"""A stand-in for the iterm2 package so save and restore can be tested with no iTerm2 running."""


class Session:
    def __init__(self, path="/work/a", job="zsh", properties=None):
        self.variables = {"path": path, "jobName": job, "profileName": "Default"}
        self.properties = properties or {"Normal Font": "Monaco 21", "Name": "Default"}
        self.sent_text = []
        self.splits = []

    async def async_get_variable(self, name):
        return self.variables.get(name)

    async def async_get_profile(self):
        outer = self
        return type("Profile", (), {"all_properties": outer.properties})()

    async def async_split_pane(self, vertical, profile_customizations):
        new_session = Session(path=profile_customizations.directory)
        self.splits.append((vertical, profile_customizations))
        return new_session

    async def async_send_text(self, text):
        self.sent_text.append(text)


class Splitter:
    def __init__(self, children, vertical=True):
        self.children, self.vertical = children, vertical


class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Size:
    def __init__(self, width, height):
        self.width, self.height = width, height


class Frame:
    def __init__(self, origin, size):
        self.origin, self.size = origin, size


class Tab:
    def __init__(self, root, title_override=""):
        self.root = root
        self.current_session = root if isinstance(root, Session) else Session()
        self.selected = False
        self.title_override = title_override
        self.title_cannot_be_set = False

    async def async_get_variable(self, name):
        return self.title_override if name == "titleOverride" else None

    async def async_set_title(self, title):
        if self.title_cannot_be_set:
            raise RuntimeError("simulated iTerm2 refusal")
        self.title_override = title

    async def async_select(self):
        self.selected = True


class Window:
    created = []
    created_windows = []
    fail_on_creation_number = None

    def __init__(self, tabs):
        self.tabs = tabs
        self.frame = Frame(Point(1, 2), Size(800, 600))
        self.frame_was_set = None

    @property
    def current_tab(self):
        return self.tabs[0]

    async def async_get_frame(self):
        return self.frame

    async def async_set_frame(self, frame):
        self.frame_was_set = frame

    @classmethod
    async def async_create(cls, connection, profile_customizations=None):
        Window.created.append(profile_customizations)
        if Window.fail_on_creation_number == len(Window.created):
            raise RuntimeError("simulated iTerm2 failure")
        window = cls([Tab(Session(path=getattr(profile_customizations, "directory", None)))])
        Window.created_windows.append(window)
        return window

    async def async_create_tab(self, profile_customizations=None):
        tab = Tab(Session(path=getattr(profile_customizations, "directory", None)))
        self.tabs.append(tab)
        return tab


class App:
    def __init__(self, terminal_windows):
        self.terminal_windows = terminal_windows


class InitialWorkingDirectory:
    INITIAL_WORKING_DIRECTORY_CUSTOM = "custom"


class LocalWriteOnlyProfile:
    def __init__(self):
        self.settings, self.directory, self.mode = {}, None, None

    def _simple_set(self, key, value):
        if key == "Unknown Setting":
            raise ValueError("unknown to this iTerm2")
        self.settings[key] = value

    def set_initial_directory_mode(self, mode):
        self.mode = mode

    def set_custom_directory(self, folder):
        self.directory = folder


_app_to_return = App([])


def set_open_windows(windows):
    global _app_to_return
    _app_to_return = App(windows)


async def async_get_app(connection):
    return _app_to_return


def run_until_complete(action, retry=False):
    import asyncio
    asyncio.run(action(object()))
