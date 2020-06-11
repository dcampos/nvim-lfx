from .core.typing import Any, Set, Dict, List, Optional, Iterator
from .core.settings import Settings
from .core.workspace import ProjectFolders
from .core.configurations import create_window_configs
from .core.sessions import Session
# from .core.windows import nop
from .core.types import config_supports_language_id, LanguageConfig, ClientConfig, ConfigRegistry
from .core.logging import debug
from .core.editor import View, Window
from .core.views import did_open, did_close, did_change, will_save, did_save
from .core.protocol import TextDocumentSyncKindIncremental


def nop(): return None


class VimDocumentHandler(object):
    def __init__(self, editor: Any, settings: Settings, workspace: ProjectFolders,
                 window: Window, configs: ConfigRegistry) -> None:
        self._editor = editor
        self._settings = settings
        self._configs = configs
        self._document_states = set()  # type: Set[str]
        self._content_states = {}  # type: Dict[str, str]
        self._pending_buffer_changes = dict()  # type: Dict[int, Dict]
        self._sessions = dict()  # type: Dict[str, List[Session]]
        self._workspace = workspace
        self._window = window
        self.changed = nop
        self.saved = nop
        self.on_attach = nop
        self.on_detach = nop

    def add_session(self, session: Session) -> None:
        self._sessions.setdefault(session.config.name, []).append(session)
        self._notify_open_documents(session)

    def remove_session(self, config_name: str) -> None:
        if config_name in self._sessions:
            del self._sessions[config_name]

    def reset(self) -> None:
        # for view in self._window.views():
        #     self._detach_view(view)
        self._document_states.clear()

    def has_document_state(self, path: str) -> bool:
        return path in self._document_states

    def _get_applicable_sessions(self, view: View) -> List[Session]:
        sessions = []  # type: List[Session]
        language_id = view.language_id()

        for config_name, config_sessions in self._sessions.items():
            for session in config_sessions:
                if config_supports_language_id(session.config, language_id):
                    if session.handles_path(view.file_name()):
                        sessions.append(session)

        return sessions

    def _notify_open_documents(self, session: Session) -> None:
        # Note: a copy is made of self._document_states because it may be modified in another thread.
        for file_name in list(self._document_states):
            if session.handles_path(file_name):
                view = self._window.find_open_file(file_name)
                if view:
                    language_id = view.language_id()
                    if config_supports_language_id(session.config, language_id):
                        sessions = self._get_applicable_sessions(view)
                        self._attach_view(view, sessions)
                        for session in sessions:
                            if session.should_notify_did_open():
                                self._notify_did_open(view, session)

    def _config_languages(self, view: View) -> Dict[str, LanguageConfig]:
        return self._configs.syntax_config_languages(view)

    def _attach_view(self, view: View, sessions: List[Session]) -> None:
        self.on_attach(view)

    def _detach_view(self, view: View) -> None:
        self.on_detach(view)

    def handle_did_open(self, view: View) -> None:
        file_name = view.file_name()
        if file_name and file_name not in self._document_states:
            config_languages = self._config_languages(view)
            if len(config_languages):
                self._document_states.add(file_name)
                # the sessions may not be available yet,
                # the document will get synced when a session is added.
                sessions = self._get_applicable_sessions(view)
                self._attach_view(view, sessions)
                for session in sessions:
                    if session.should_notify_did_open():
                        self._notify_did_open(view, session)

    def _notify_did_open(self, view: View, session: Session) -> None:
        language_id = view.language_id()
        if session.client:
            # mypy: expected editor.View, got View
            session.client.send_notification(did_open(view, language_id))  # type: ignore

    def handle_did_close(self, view: View) -> None:
        file_name = view.file_name() or ""
        debug("Handling did_close", file_name)
        try:
            self._document_states.remove(file_name)
        except KeyError:
            return
        # mypy: expected editor.View, got View
        notification = did_close(view)  # type: ignore
        for session in self._get_applicable_sessions(view):
            if session.client and session.should_notify_did_close():
                session.client.send_notification(notification)

    def handle_will_save(self, view: View, reason: int) -> None:
        file_name = view.file_name()
        if file_name in self._document_states:
            for session in self._get_applicable_sessions(view):
                if session.client and session.should_notify_will_save():
                    # mypy: expected editor.View, got View
                    session.client.send_notification(will_save(view, reason))  # type: ignore

    def handle_did_save(self, view: View) -> None:
        file_name = view.file_name()
        if file_name in self._document_states:
            self.purge_changes(view)
            for session in self._get_applicable_sessions(view):
                if session.client:
                    send_did_save, include_text = session.should_notify_did_save()
                    if send_did_save:
                        # mypy: expected editor.View, got View
                        session.client.send_notification(did_save(view, include_text))  # type: ignore
            self.saved()
        else:
            debug('document not tracked', file_name)

    def handle_did_change(self, view: View) -> None:
        buffer_id = view.buffer_id()
        change_count = view.change_count()
        if buffer_id in self._pending_buffer_changes:
            self._pending_buffer_changes[buffer_id]["version"] = change_count
        else:
            self._pending_buffer_changes[buffer_id] = {"view": view, "version": change_count}
        self._editor.set_timeout_async(lambda: self.purge_did_change(buffer_id, change_count), 50)

    def purge_changes(self, view: View) -> None:
        self.purge_did_change(view.buffer_id())

    def purge_did_change(self, buffer_id: int, buffer_version: Optional[int] = None) -> None:
        if buffer_id not in self._pending_buffer_changes:
            return

        pending_buffer = self._pending_buffer_changes.get(buffer_id)

        if pending_buffer:
            if buffer_version is None or buffer_version == pending_buffer["version"]:
                self.notify_did_change(pending_buffer["view"])
                self.changed()

    def notify_did_change(self, view: View) -> None:
        if not view.is_valid():
            return

        config_languages = self._config_languages(view)

        if not len(config_languages):
            return

        file_name = view.file_name()
        if file_name and view.window() == self._window:
            # ensure view is opened.
            if file_name not in self._document_states:
                self.handle_did_open(view)

            if view.buffer_id() in self._pending_buffer_changes:
                del self._pending_buffer_changes[view.buffer_id()]
                previous_content = self._content_states.get(file_name, '')
                # mypy: expected editor.View, got View
                for session in self._get_applicable_sessions(view):
                    if session.client and file_name in self._document_states and session.should_notify_did_change():
                        if session.text_sync_kind() == TextDocumentSyncKindIncremental:
                            session.client.send_notification(did_change(view, previous_content))
                        else:
                            # Full sync
                            session.client.send_notification(did_change(view))
                self._content_states[file_name] = view.entire_content()


class VimConfigManager(object):

    def __init__(self, window: Window, global_configs: List[ClientConfig]) -> None:
        self._window = window
        self._global_configs = global_configs
        self._temp_disabled_configs = []  # type: List[str]
        self.all = create_window_configs(window, global_configs)

    def is_supported(self, view: View) -> bool:
        return any(self.scope_configs(view))

    def scope_configs(self, view: View, point: Optional[int] = None) -> Iterator[ClientConfig]:
        return self.syntax_configs(view)

    def syntax_configs(self, view: View, include_disabled: bool = False) -> List[ClientConfig]:
        language_id = view.language_id()
        return list(filter(lambda c: config_supports_language_id(c, language_id)
                           and (c.enabled or include_disabled), self.all))

    def syntax_supported(self, view: View) -> bool:
        language_id = view.language_id()
        for found in filter(lambda c: config_supports_language_id(c, language_id) and c.enabled, self.all):
            return True
        return False

    def syntax_config_languages(self, view: View) -> Dict[str, LanguageConfig]:
        language_id = view.language_id()
        config_languages = {}
        for config in self.all:
            if config.enabled:
                for language in config.languages:
                    if language.id == language_id:
                        config_languages[config.name] = language
        return config_languages

    def update(self) -> None:
        self.all = create_window_configs(self._window, self._global_configs)
        for config in self.all:
            if config.name in self._temp_disabled_configs:
                config.enabled = False

    def enable_config(self, config_name: str) -> None:
        # TODO enable_in_project(self._window, config_name)
        self.update()

    def disable_config(self, config_name: str) -> None:
        # TODO disable_in_project(self._window, config_name)
        self.update()

    def disable_temporarily(self, config_name: str) -> None:
        self._temp_disabled_configs.append(config_name)
        self.update()
