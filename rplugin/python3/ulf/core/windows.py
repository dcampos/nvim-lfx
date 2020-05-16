from .rpc import Client
from .sessions import Session
from .types import ViewLike
from .types import WindowLike
from .typing import Any, Protocol


class LanguageHandlerListener(Protocol):

    def on_start(self, config_name: str, window: WindowLike) -> bool:
        ...

    def on_initialized(self, config_name: str, window: WindowLike, client: Client) -> None:
        ...


class DocumentHandler(Protocol):
    def add_session(self, session: Session) -> None:
        ...

    def remove_session(self, config_name: str) -> None:
        ...

    def reset(self) -> None:
        ...

    def handle_did_open(self, view: ViewLike) -> None:
        ...

    def handle_did_change(self, view: ViewLike) -> None:
        ...

    def purge_changes(self, view: ViewLike) -> None:
        ...

    def handle_will_save(self, view: ViewLike, reason: int) -> None:
        ...

    def handle_did_save(self, view: ViewLike) -> None:
        ...

    def handle_did_close(self, view: ViewLike) -> None:
        ...

    def has_document_state(self, file_name: str) -> bool:
        ...

def nop() -> None:
    pass


def extract_message(params: Any) -> str:
    return params.get("message", "???") if isinstance(params, dict) else "???"
