from .core.typing import List, Dict, Any, Callable, Optional
from .core.types import WindowLike, ViewLike, ClientStates, ConfigRegistry
from .core.workspace import ProjectFolders, get_workspace_folders, enable_in_project, disable_in_project, sorted_workspace_folders
from .core.settings import Settings
from .core.configurations import ClientConfig
from .core.diagnostics import DiagnosticsStorage
from .core.windows import LanguageHandlerListener, DocumentHandler, extract_message
from .core.sessions import Session
from .core.logging import debug
from .core.message_request_handler import MessageRequestHandler
from .core.rpc import Client, Response, EditorLogger, Notification
from .core.edit import parse_workspace_edit

import threading

class DummyLanguageHandlerDispatcher(object):

    def on_start(self, config_name: str, window: WindowLike) -> bool:
        return True

    def on_initialized(self, config_name: str, window: WindowLike, client: Client) -> None:
        pass

class ContextManager(object):
    def __init__(
        self,
        window: WindowLike,
        workspace: ProjectFolders,
        settings: Settings,
        configs: ConfigRegistry,
        documents: DocumentHandler,
        diagnostics: DiagnosticsStorage,
        session_starter: Callable,
        editor: Any,
        handler_dispatcher: LanguageHandlerListener,
        on_closed: Optional[Callable] = None,
        server_panel_factory: Optional[Callable] = None
    ) -> None:
        self._window = window
        self._settings = settings
        self._configs = configs
        self.diagnostics = diagnostics
        self.documents = documents
        self.server_panel_factory = server_panel_factory
        self._sessions = dict()  # type: Dict[str, List[Session]]
        self._next_initialize_views = list()  # type: List[ViewLike]
        self._start_session = session_starter
        self._editor = editor
        self._handlers = handler_dispatcher
        self._restarting = False
        self._on_closed = on_closed
        self._is_closing = False
        self._initialization_lock = threading.Lock()
        self._workspace = workspace
        self._workspace.on_changed = self._on_project_changed
        self._workspace.on_switched = self._on_project_switched

    def _on_project_changed(self, folders: List[str]) -> None:
        workspace_folders = get_workspace_folders(self._workspace.folders)
        for config_name in self._sessions:
            for session in self._sessions[config_name]:
                session.update_folders(workspace_folders)

    def _on_project_switched(self, folders: List[str]) -> None:
        debug('project switched - ending all sessions')
        self.end_sessions()

    def get_session(self, config_name: str, file_path: str) -> Optional[Session]:
        return self._find_session(config_name, file_path)

    def _is_session_ready(self, config_name: str, file_path: str) -> bool:
        maybe_session = self._find_session(config_name, file_path)
        return maybe_session is not None and maybe_session.state == ClientStates.READY

    def _can_start_config(self, config_name: str, file_path: str) -> bool:
        return not bool(self._find_session(config_name, file_path))

    def _find_session(self, config_name: str, file_path: str) -> Optional[Session]:
        if config_name in self._sessions:
            for session in self._sessions[config_name]:
                if session.handles_path(file_path):
                    return session
        return None

    def update_configs(self) -> None:
        self._configs.update()

    def enable_config(self, config_name: str) -> None:
        enable_in_project(self._window, config_name)
        self.update_configs()
        self._editor.set_timeout_async(self.start_active_views, 500)
        self._window.status_message("{} enabled, starting server...".format(config_name))

    def disable_config(self, config_name: str) -> None:
        disable_in_project(self._window, config_name)
        self.update_configs()
        self.end_config_sessions(config_name)

    def start_active_views(self) -> None:
        active_views = [] # TODO get_active_views(self._window)
        debug('window {} starting {} initial views'.format(self._window.id(), len(active_views)))
        for view in active_views:
            if view.file_name():
                self._workspace.update()
                self._initialize_on_open(view)
                self.documents.handle_did_open(view)

    def activate_view(self, view: ViewLike) -> None:
        file_name = view.file_name() or ""
        debug("Activating view {}".format(file_name))
        if not self.documents.has_document_state(file_name):
            self._workspace.update()
            self._initialize_on_open(view)

    def _open_after_initialize(self, view: ViewLike) -> None:
        if any(v for v in self._next_initialize_views if v.id() == view.id()):
            return
        self._next_initialize_views.append(view)

    def _open_pending_views(self) -> None:
        opening = list(self._next_initialize_views)
        self._next_initialize_views = []
        for view in opening:
            debug('opening after initialize', view.file_name())
            self._initialize_on_open(view)

    def _initialize_on_open(self, view: ViewLike) -> None:
        """Takes a view and ensures all needed configs are scheduled for starting"""

        file_path = view.file_name() or ""

        debug('Going to initialize {}, folders: {}'.format(file_path, self._workspace.folders))

        if not self._workspace.includes_path(file_path):
            return

        debug('Path included - {}'.format(file_path))

        def needed_configs(configs: 'List[ClientConfig]') -> 'List[ClientConfig]':
            debug('needed_configs - configs: {}'.format(configs))
            new_configs = []
            for c in configs:
                if c.name not in self._sessions:
                    new_configs.append(c)
                else:
                    session = next((s for s in self._sessions[c.name] if s.handles_path(file_path)), None)
                    if session:
                        if session.state != ClientStates.READY:
                            debug('scheduling for delayed open, session {} not ready: {}'.format(c.name, file_path))
                            self._open_after_initialize(view)
                        else:
                            debug('found ready session {} for {}'.format(c.name, file_path))
                    else:
                        debug('path not in existing {} session: {}'.format(c.name, file_path))
                        new_configs.append(c)

            return new_configs

        # have all sessions for this document been started?
        with self._initialization_lock:
            new_configs = needed_configs(self._configs.syntax_configs(view, include_disabled=True))

            if any(new_configs):
                # TODO: cannot observe project setting changes
                # have to check project overrides every session request
                self.update_configs()

                startable_configs = needed_configs(self._configs.syntax_configs(view))

                for config in startable_configs:

                    debug("window {} requests {} for {}".format(self._window.id(), config.name, file_path))
                    self._start_client(config, file_path)

    def _start_client(self, config: ClientConfig, file_path: str) -> None:
        if not self._can_start_config(config.name, file_path):
            debug('Already starting on this window:', config.name)
            return

        if not self._handlers.on_start(config.name, self._window):
            return

        self._window.status_message("Starting " + config.name + "...")
        session = None  # type: Optional[Session]
        workspace_folders = sorted_workspace_folders(self._workspace.folders, file_path)
        try:
            debug("going to start {}".format(config.name))
            session = self._start_session(
                self._window,                  # window
                workspace_folders,             # workspace_folders
                config,                        # config
                self._handle_pre_initialize,   # on_pre_initialize
                self._handle_post_initialize,  # on_post_initialize
                self._handle_post_exit,        # on_post_exit
                lambda msg: self._handle_stderr_log(config.name, msg))  # on_stderr_log
        except Exception as e:
            message = "\n\n".join([
                "Could not start {}",
                "{}",
                "Server will be disabled for this window"
            ]).format(config.name, str(e))

            self._configs.disable_temporarily(config.name)
            self._editor.message_dialog(message)

        if session:
            debug("window {} added session {}".format(self._window.id(), config.name))
            self._sessions.setdefault(config.name, []).append(session)

    def _handle_message_request(self, params: dict, source: str, client: Client, request_id: Any) -> None:
        handler = MessageRequestHandler(self._window.active_view(), client, request_id, params, source)  # type: ignore
        handler.show()

    def restart_sessions(self) -> None:
        self._restarting = True
        self.end_sessions()

    def end_sessions(self) -> None:
        self.documents.reset()
        for config_name in list(self._sessions):
            self.end_config_sessions(config_name)

    def end_config_sessions(self, config_name: str) -> None:
        config_sessions = self._sessions.pop(config_name, [])
        for session in config_sessions:
            debug("unloading session", config_name)
            session.end()

    def get_project_path(self, file_path: str) -> Optional[str]:
        candidate = None  # type: Optional[str]
        for folder in self._workspace.folders:
            if file_path.startswith(folder):
                if candidate is None or len(folder) > len(candidate):
                    candidate = folder
        return candidate

    def _apply_workspace_edit(self, params: Dict[str, Any], client: Client, request_id: int) -> None:
        edit = params.get('edit', dict())
        changes = parse_workspace_edit(edit)
        self._window.run_command('lsp_apply_workspace_edit', {'changes': changes})
        # TODO: We should ideally wait for all changes to have been applied.
        # This however seems overly complicated, because we have to bring along a string representation of the
        # client through the editor-command invocations (as well as the request ID, but that is easy), and then
        # reconstruct/get the actual Client object back. Maybe we can (ab)use our homebrew event system for this?
        client.send_response(Response(request_id, {"applied": True}))

    def _payload_log_sink(self, message: str) -> None:
        self._editor.set_timeout_async(lambda: self._handle_server_message(":", message), 0)

    def _handle_pre_initialize(self, session: Session) -> None:
        client = session.client
        client.set_crash_handler(lambda: self._handle_server_crash(session.config))
        client.set_error_display_handler(self._window.status_message)

        if self.server_panel_factory and isinstance(client.logger, EditorLogger):
            client.logger.server_name = session.config.name
            client.logger.sink = self._payload_log_sink

        client.on_request(
            "window/showMessageRequest",
            lambda params, request_id: self._handle_message_request(params, session.config.name, client, request_id))

        client.on_notification(
            "window/showMessage",
            lambda params: self._handle_show_message(session.config.name, params))

        client.on_notification(
            "window/logMessage",
            lambda params: self._handle_log_message(session.config.name, params))

    def _handle_post_initialize(self, session: Session) -> None:

        # handle server requests and notifications
        session.on_request(
            "workspace/applyEdit",
            lambda params, request_id: self._apply_workspace_edit(params, session.client, request_id))

        session.on_notification(
            "textDocument/publishDiagnostics",
            lambda params: self.diagnostics.receive(session.config.name, params))

        self._handlers.on_initialized(session.config.name, self._window, session.client)

        session.client.send_notification(Notification.initialized())

        document_sync = session.capabilities.get("textDocumentSync")
        if document_sync:
            self.documents.add_session(session)
        self._window.status_message("{} initialized".format(session.config.name))

        self._open_pending_views()

    def handle_view_closed(self, view: ViewLike) -> None:
        if view.file_name():
            if not self._is_closing:
                if not self._window.is_valid():
                    # try to detect close synchronously (for quitting)
                    self._handle_window_closed()
                else:
                    # in case the window is invalidated after the last view is closed
                    self._editor.set_timeout_async(lambda: self._check_window_closed(), 100)

    def _check_window_closed(self) -> None:
        if not self._is_closing and not self._window.is_valid():
            self._handle_window_closed()

    def _handle_window_closed(self) -> None:
        debug('window {} closed, ending sessions'.format(self._window.id()))
        self._is_closing = True
        self.end_sessions()

    def _handle_all_sessions_ended(self) -> None:
        debug('clients for window {} unloaded'.format(self._window.id()))
        if self._restarting:
            debug('window {} sessions unloaded - restarting'.format(self._window.id()))
            self.start_active_views()
        elif not self._window.is_valid():
            debug('window {} closed and sessions unloaded'.format(self._window.id()))
            if self._on_closed:
                self._on_closed()

    def _handle_post_exit(self, config_name: str) -> None:
        self.documents.remove_session(config_name)
        debug('views: {}'.format(self._window.views()))
        for view in self._window.views():
            file_name = view.file_name()
            if file_name:
                self.diagnostics.remove(file_name, config_name)

        debug("session", config_name, "ended")
        if not self._sessions:
            self._handle_all_sessions_ended()

    def _handle_server_crash(self, config: ClientConfig) -> None:
        msg = "Language server {} has crashed, do you want to restart it?".format(config.name)
        result = self._editor.ok_cancel_dialog(msg, ok_title="Restart")
        if result == self._editor.DIALOG_YES:
            self.restart_sessions()

    def _handle_server_message(self, name: str, message: str) -> None:
        debug("{}: {}".format(name, message))

    def _handle_log_message(self, name: str, params: Any) -> None:
        self._handle_server_message(name, extract_message(params))

    def _handle_stderr_log(self, name: str, message: str) -> None:
        if self._settings.log_stderr:
            self._handle_server_message(name, message)

    def _handle_show_message(self, name: str, params: Any) -> None:
        self._editor.status_message("{}: {}".format(name, extract_message(params)))
