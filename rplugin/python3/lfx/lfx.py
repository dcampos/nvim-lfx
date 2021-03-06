import importlib
import os.path
import pynvim
import abc
import json
from pynvim import Nvim

from .core.typing import Dict, List, Callable, Optional, Any, Iterator
from .core.settings import settings, ClientConfigs, ClientConfig
from .core.sessions import create_session, Session
from .core.protocol import WorkspaceFolder, Point, Range, RequestMethod, Request
from .core.logging import set_log_file, set_debug_logging, set_exception_logging, debug
from .core.workspace import ProjectFolders
from .core.diagnostics import DiagnosticsStorage
from .core.rpc import Client
from .core.clients import get_window_env
from .core.edit import parse_text_edit, sort_by_application_order
from .documents import VimDocumentHandler, VimConfigManager
from .editor import VimEditor, VimWindow, VimView
from .context import ContextManager
from .diagnostics import DiagnosticsPresenter
from .util import to_char_index, debounce


@pynvim.plugin
class LFX:

    def __init__(self, vim: Nvim):
        self.vim = vim
        vars = self.vim.vars
        self.settings = settings
        self.settings.log_debug = vars.get('lfx#log#debug', True)
        self.settings.log_payloads = vars.get('lfx#log#payloads', False)
        self.settings.log_server = vars.get('lfx#log#server', False)
        self.settings.log_stderr = vars.get('lfx#log#stderr', True)
        self.log_file = vars.get('lfx#log#file')
        set_log_file(self.log_file)
        set_exception_logging(True)
        set_debug_logging(True)
        self.client_configs = ClientConfigs()  # type: ClientConfigs
        self._update_configs()
        self.root_patterns = vars.get('lfx#root_patterns', {'*': ['.gitmodules', '.git']})
        self.editor = VimEditor(self)
        self.window = VimWindow(self.editor)
        self.config_manager = VimConfigManager(self.window, self.client_configs.all)
        self.documents = VimDocumentHandler(self.editor, self.settings, None, self.window,
                                            self.config_manager)
        self.documents.on_attach = self._on_attach
        self.documents.on_detach = self._on_detach

        def start_session(window: VimWindow,
                          workspace_folders: List[WorkspaceFolder],
                          config: ClientConfig,
                          on_pre_initialize: Callable[[Session], None],
                          on_post_initialize: Callable[[Session], None],
                          on_post_exit: Callable[[str], None],
                          on_stderr_log: Optional[Callable[[str], None]]) -> Optional[Session]:
            _, env = get_window_env(window, config)
            return create_session(
                config=config,
                workspace_folders=workspace_folders,
                env=env,
                settings=settings,
                on_pre_initialize=on_pre_initialize,
                on_post_initialize=lambda session: self.vim.async_call(on_post_initialize, session),
                on_post_exit=on_post_exit,
                on_stderr_log=on_stderr_log)

        import_helpers(self.vim.funcs.globpath(self.vim.options['runtimepath'],
                                               'rplugin/python3/lfx/helper/*.py'))

        self.diagnostics_presenter = DiagnosticsPresenter(self.window, self.documents)
        self.diagnostics = DiagnosticsStorage(self.diagnostics_presenter)

        self.manager = ContextManager(
            self.window,
            ProjectFolders(self.window),
            self.settings,
            self.config_manager,
            self.documents,
            self.diagnostics,
            start_session,
            self.editor,
            ClientHelperDispacher(self, self.vim))

        # instances = RequestHelper.instantiate_all(self, vim)
        # debug('instances = %s' % instances)

        self.vim.vars['lfx#_channel_id'] = self.vim.channel_id

    def _on_attach(self, view: VimView) -> None:
        debug('attached buffer %d' % view.buffer_id())
        self.vim.call('lfx#attach_buffer', view.buffer_id())
        self.vim.vars['lfx#attached_bufnr'] = view.buffer_id()
        self.vim.command('doautocmd <nomodeline> User LFXAttachBuffer')
        del self.vim.vars['lfx#attached_bufnr']

    def _on_detach(self, view: VimView) -> None:
        pass

    @pynvim.function('LFX_handle_did_open', sync=True, eval='expand("<abuf>")')
    def _on_did_open(self, args, bufnr):
        debug('buffer {} opened'.format(bufnr))
        view = self.window.view_for_buffer(int(bufnr))
        self.manager.activate_view(view)
        self.documents.handle_did_open(view)

    @pynvim.function('LFX_handle_will_save', eval='expand("<abuf>")')
    def _on_will_save(self, args, bufnr):
        view = self.window.view_for_buffer(int(bufnr))
        self.documents.handle_will_save(view, reason=1)

    @pynvim.function('LFX_handle_did_save', eval='expand("<abuf>")')
    def _on_did_save(self, args, bufnr):
        view = self.window.view_for_buffer(int(bufnr))
        self.documents.handle_did_save(view)

    @pynvim.function('LFX_handle_did_change', eval='expand("<abuf>")')
    def _on_did_change(self, args, bufnr):
        view = self.window.view_for_buffer(int(bufnr))
        self.documents.handle_did_change(view)

    @pynvim.function('LFX_handle_did_close', eval='expand("<abuf>")')
    def _on_did_close(self, args, bufnr):
        if not self.vim.api.buf_is_loaded(int(bufnr)):
            return

        view = self.window.view_for_buffer(int(bufnr), False)
        debug("Event: did_close - %s" % (bufnr))

        if view:
            self.manager.handle_view_closed(view)
            self.documents.handle_did_close(view)
            self.window.close_view(int(bufnr))

    @pynvim.function('LFX_handle_leave', sync=True)
    def _on_vimleave(self, args):
        self.window.valid = False
        self.manager.end_sessions()

    @pynvim.function('LFX_handle_complete_done', sync=True)
    def _on_complete_done(self, args):
        resolved_item = self.vim.vars.get('lfx#completion#_resolved_item')
        completed_item = self.vim.vvars.get('completed_item')
        if completed_item and resolved_item:
            view = self.window.active_view()
            edits = resolved_item.get('additionalTextEdits')
            if edits:
                edits = sort_by_application_order(map(parse_text_edit, edits))
                self.editor.apply_document_edits(view.file_name(), edits)

    @pynvim.function('LFX_hover')
    def hover(self, args):
        self._send_request(RequestMethod.HOVER, *args)

    @pynvim.function('LFX_signature_help')
    def signature_help(self, args):
        self._send_request(RequestMethod.SIGNATURE_HELP, *args)

    @pynvim.function('LFX_goto_definition')
    def goto_definition(self, args):
        self._send_request(RequestMethod.DEFINITION, *args)

    @pynvim.function('LFX_goto_type_definition')
    def goto_type_definition(self, args):
        self._send_request(RequestMethod.TYPE_DEFINITION, *args)

    @pynvim.function('LFX_goto_implementation')
    def goto_implementation(self, args):
        self._send_request(RequestMethod.IMPLEMENTATION, *args)

    @pynvim.function('LFX_goto_declaration')
    def goto_declaration(self, args):
        self._send_request(RequestMethod.DECLARATION, *args)

    @pynvim.function('LFX_workspace_symbol', sync=True)
    def workspace_symbol(self, args):
        self._send_request(RequestMethod.WORKSPACE_SYMBOL, *args)

    @pynvim.function('LFX_document_symbol', sync=True)
    def document_symbol(self, args):
        self._send_request(RequestMethod.DOCUMENT_SYMBOL, *args)

    @pynvim.function('LFX_references')
    def references(self, args):
        self._send_request(RequestMethod.REFERENCES, *args)

    @pynvim.function('LFX_document_highlight')
    def document_highlight(self, args):
        self._send_request(RequestMethod.DOCUMENT_HIGHLIGHT, *args)

    @pynvim.function('LFX_document_color')
    def document_color(self, args):
        self._send_request(RequestMethod.DOCUMENT_COLOR, *args)

    @pynvim.function('LFX_rename')
    def rename(self, args):
        self._send_request(RequestMethod.RENAME, *args)

    @pynvim.function('LFX_prepare_rename', sync=True)
    def prepare_rename(self, args):
        self._send_request(RequestMethod.PREPARE_RENAME, *args)

    @pynvim.function('LFX_format')
    def format(self, args):
        self._send_request(RequestMethod.FORMATTING, *args)

    @pynvim.function('LFX_format_range')
    def format_range(self, args):
        self._send_request(RequestMethod.RANGE_FORMATTING, *args)

    @pynvim.function('LFX_code_actions')
    def code_actions(self, args):
        self._send_request(RequestMethod.CODE_ACTION, *args)

    @pynvim.function('LFX_complete')
    def complete(self, args):
        self._send_request(RequestMethod.COMPLETION, *args)

    @pynvim.function('LFX_complete_sync', sync=True)
    def complete_sync(self, args):
        debug(args)
        self._send_request(RequestMethod.COMPLETION, *args)

    @pynvim.function('LFX_resolve_completion', sync=True)
    def resolve_completion(self, args: List[Dict[str, Any]] = [{}]):
        self._send_request(RequestMethod.RESOLVE, *args)

    @pynvim.function('LFX_show_diagnostics')
    def show_diagnostics(self, args):
        bufnr = int(args[0])
        if bufnr == -1:
            return
        view = self.window.view_for_buffer(bufnr)
        if view:
            self.diagnostics_presenter.show_all(view.file_name())

    @pynvim.function('LFX_send_request', sync=True)
    def send_request(self, args):
        self._send_request(*args)

    def _send_request(self, method, opts={}, sync=False, wait=0):
        debug('_send_request, method={}, opts={}, sync={}'.format(method, opts, sync))
        helper = RequestHelper.for_method(method)
        if helper:
            instance = helper(self, self.vim)

            if not instance.is_enabled():
                return

            if sync:
                instance.run_sync(opts)
            elif wait:
                call_id = f'{method}:{json.dumps(opts, sort_keys=True)}'
                debounce(wait, call_id, lambda: self.vim.async_call(instance.run, opts))
            else:
                instance.run(opts)
        else:
            debug('No helper found for method={}'.format(method))

    def _update_configs(self) -> None:
        configs = self.vim.vars.get('lfx#configs', {})
        for config in configs.values():
            config['languages'] = []
            for filetype in config.get('filetypes', []):
                # TODO: convert appropriately
                config['languages'].append({'languageId': filetype})
        self.client_configs.update({'clients': configs})

    def session_for_view(self, view: VimView, capability: str = None) -> Optional[Session]:
        return next(self.sessions_for_view(view, capability), None)

    def sessions_for_view(self, view: VimView, capability: str = None) -> Iterator[Session]:
        for config in self.client_configs.all:
            for language in config.languages:
                if language.id == view.language_id():
                    session = self.manager.get_session(config.name, view.file_name())
                    if session and (not capability or session.has_capability(capability)):
                        yield session


def import_helpers(runtime: str) -> None:
    paths: List[str] = runtime.split('\n')

    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        module_name = 'lfx.helper.%s' % name
        spec = importlib.util.spec_from_file_location(module_name, p)

        if spec:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)


class RequestHelper(metaclass=abc.ABCMeta):
    _registry = {}

    def __init__(self, lfx: LFX, vim: Nvim) -> None:
        self.lfx = lfx
        self.vim = vim

    def current_view(self) -> VimView:
        bufnr = self.vim.current.buffer.number
        return self.lfx.window.view_for_buffer(int(bufnr))

    def cursor_point(self) -> Point:
        cursor = self.vim.current.window.cursor
        debug('cursor => %s' % cursor)
        return self._create_point(*cursor)

    def selection_range(self) -> Range:
        begin = self.vim.current.buffer.mark('<')
        end = self.vim.current.buffer.mark('>')
        return Range(self._create_point(*begin), self._create_point(*end))

    def _create_point(self, row: int, col: int) -> Point:
        row -= 1
        line_text = self.vim.current.buffer[row]
        col = to_char_index(line_text, col)
        return Point(row, col)

    def is_enabled(self) -> bool:
        """Should check if the helper should run."""
        return True

    @property
    def capability(self) -> Optional[str]:
        """Needed capability for this request"""
        return self._capability

    def params(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """Prepare params for the request"""
        return None

    def run(self, options: Dict[str, Any] = {}):
        params = self.params(options)
        view = self.current_view()
        session = self.lfx.session_for_view(view, self.capability)
        method = self._method
        if session is not None:
            self.lfx.documents.purge_changes(view)
            session.client.send_request(Request(method, params),
                                        lambda res: self.vim.async_call(
                                            self.dispatch_response, res, options),
                                        lambda res: debug(res))
        else:
            self.lfx.editor.error_message('Not available!')

    def run_sync(self, options: Dict[str, Any]):
        params = self.params(options)
        view = self.current_view()
        session = self.lfx.session_for_view(view, self._capability)
        method = self._method
        if session is not None:
            self.lfx.documents.purge_changes(view)
            session.client.execute_request(Request(method, params),
                                           lambda res: self.dispatch_response(res, options),
                                           lambda res: debug(res))
        else:
            self.lfx.editor.error_message('Not available!')

    def dispatch_response(self, response, options):
        """Dispatches the response according to the options passed"""

        debug(response)

        if not response:
            return

        if options.get('process_response', False):
            response = self.process_response(response, options)

        target = options.get('target')

        if target:
            self.vim.vars[target] = response

        callback = options.get('callback')

        if callback:
            include_results = options.get('include_results', True)
            if include_results:
                self.vim.call(callback, response)
            else:
                self.vim.call(callback)

        if not callback and not target:
            self.handle_response(response)

    @abc.abstractmethod
    def handle_response(self, response):
        pass

    def process_response(self, response, options) -> Any:
        """Should process the response and return the processed value. NOT mandatory.
        """
        return response

    @classmethod
    def instance(cls, lfx, vim, *args, **kwargs) -> 'RequestHelper':
        try:
            return cls._instance
        except AttributeError:
            cls._instance = cls(lfx, vim, *args, **kwargs)
            return cls._instance

    @classmethod
    def for_method(cls, method: str) -> 'RequestHelper':
        helper = cls._registry.get(method)
        return helper

    def __init_subclass__(cls, method=None, capability=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._method = method
        cls._capability = capability
        cls._registry[method] = cls


class ClientHelper(metaclass=abc.ABCMeta):
    _registry_by_name: Dict[str, Any] = {}
    _registry_generic: List[Any] = []

    def __init__(self, lfx, vim):
        self.lfx = lfx
        self.vim = vim

    def setup(self, config_name: str, window: VimWindow, view: VimView) -> bool:
        return True

    def on_initialized(self, config_name: str, window: VimWindow, client: Client) -> None:
        pass

    def on_exited(self, config_name: str, window: VimWindow) -> None:
        pass

    @classmethod
    def for_name(cls, config_name: str = None) -> 'List[ClientHelper]':
        try:
            return [cls._registry_by_name[config_name]] + cls._registry_generic
        except KeyError:
            return cls._registry_generic

    @classmethod
    def instance(cls, lfx, vim, *args, **kwargs) -> 'ClientHelper':
        try:
            return cls._instance
        except AttributeError:
            cls._instance = cls(lfx, vim, *args, **kwargs)
            return cls._instance

    def __init_subclass__(cls, config_name=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if config_name:
            cls._registry_by_name[config_name] = cls
        else:
            cls._registry_generic.append(cls)


class ClientHelperDispacher(object):

    def __init__(self, lfx, vim):
        self.lfx = lfx
        self.vim = vim

    def _helper_instances(self, config_name) -> List[ClientHelper]:
        return list(map(lambda cls: cls.instance(self.lfx, self.vim),
                        ClientHelper.for_name(config_name)))

    def setup(self, config_name: str, window: VimWindow, view: VimView) -> bool:
        helpers = self._helper_instances(config_name)
        return all(helper.setup(config_name, window, view)
                   for helper in helpers) if helpers else True

    def on_initialized(self, config_name: str, window: VimWindow, client: Client) -> None:
        helpers = self._helper_instances(config_name)
        for helper in helpers:
            helper.on_initialized(config_name, window, client)

    def on_exited(self, config_name: str, window: VimWindow) -> None:
        helpers = self._helper_instances(config_name)
        for helper in helpers:
            helper.on_exited(config_name, window)


class DiagnosticsHelper(ClientHelper):

    def on_initialized(self, config_name: str, window: VimWindow, client: Client) -> None:
        client.on_notification(
            "textDocument/publishDiagnostics",
            lambda params: self.lfx.diagnostics.receive(config_name, params))

    def on_exited(self, config_name: str, window: VimWindow) -> None:
        debug('on_exited called: %s' % config_name)
        for view in window.views():
            file_name = view.file_name()
            if file_name:
                self.diagnostics.remove(file_name, config_name)
