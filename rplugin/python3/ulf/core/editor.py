from .typing import Optional, Any, Dict, List, Callable
import abc


class Settings:
    pass


class Region:
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b


DIALOG_YES = 'yes'


class Editor(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def set_timeout_async(self, f: Callable, timeout_ms: int = 0) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def message_dialog(self, message) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def status_message(self, message) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def ok_cancel_dialog(self, msg, ok_title=None) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def expand_variables(self, value, variables) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def windows(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def active_window(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def show_message_request(self, source, message_type, message, titles, on_result):
        raise NotImplementedError()


class View(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def id(self) -> int:
        raise NotImplementedError()

    @abc.abstractmethod
    def file_name(self) -> Optional[str]:
        raise NotImplementedError()

    @abc.abstractmethod
    def change_count(self) -> int:
        raise NotImplementedError()

    @abc.abstractmethod
    def window(self) -> Optional[Any]:  # WindowLike
        raise NotImplementedError()

    @abc.abstractmethod
    def buffer_id(self) -> int:
        raise NotImplementedError()

    @abc.abstractmethod
    def set_status(self, key: str, status: str) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def language_id(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def entire_content(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def tab_size(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def translate_tabs_to_spaces(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def is_valid(self):
        raise NotImplementedError()


class Window(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def id(self) -> int:
        raise NotImplementedError()

    @abc.abstractmethod
    def is_valid(self) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def folders(self) -> List[str]:
        raise NotImplementedError()

    @abc.abstractmethod
    def find_open_file(self, path: str) -> Optional[View]:
        raise NotImplementedError()

    @abc.abstractmethod
    def active_view(self) -> Optional[View]:
        raise NotImplementedError()

    @abc.abstractmethod
    def status_message(self, msg: str) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def views(self) -> List[View]:
        raise NotImplementedError()

    @abc.abstractmethod
    def run_command(self, command_name: str, command_args: Dict[str, Any]) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def extract_variables(self):
        raise NotImplementedError()
