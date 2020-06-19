import importlib
import os.path
import pynvim
import abc
from pynvim import Nvim

from .core.typing import Dict, List, Callable, Optional, Any, Iterator
from .core.settings import settings, ClientConfigs, ClientConfig
from .core.sessions import create_session, Session
from .core.protocol import WorkspaceFolder, Point, Range, RequestMethod
from .core.logging import set_log_file, set_debug_logging, set_exception_logging, debug
from .core.workspace import ProjectFolders
from .core.diagnostics import DiagnosticsStorage
from .core.rpc import Client
from .documents import VimDocumentHandler, VimConfigManager
from .editor import VimEditor, VimWindow, VimView
from .context import ContextManager
from .diagnostics import DiagnosticsPresenter
from .util import to_char_index


@pynvim.plugin
class ULF:

    def __init__(self, vim: Nvim):
        self.vim = vim
        vars = self.vim.vars
        self.settings = settings
        self.settings.log_debug = True
        self.settings.log_payloads = True
        self.settings.log_server = True
        self.settings.log_stderr = True
        self.log_file = vars.get('ulf#log_file', '/tmp/ulf.log')
        set_log_file(self.log_file)
        set_exception_logging(True)
        set_debug_logging(True)
        self.client_configs = ClientConfigs()  # type: ClientConfigs
        self._update_configs()
        self.root_patterns = vars.get('ulf#root_paterns', {'*': ['.gitmodules', '.git']})
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
            return create_session(
                config=config,
                workspace_folders=workspace_folders,
                env=dict(),
                settings=settings,
                on_pre_initialize=on_pre_initialize,
                on_post_initialize=lambda session: self.vim.async_call(on_post_initialize, session),
                on_post_exit=lambda config_name: debug('session ended: ' + config_name),
                on_stderr_log=on_stderr_log)

        import_helpers(self.vim.funcs.globpath(self.vim.options['runtimepath'],
                                               'rplugin/python3/ulf/helper/*.py'))

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

        # debug('helpers = %s' % _HELPERS)

        # instances = RequestHelper.instantiate_all(self, vim)
        # debug('instances = %s' % instances)

        self.vim.vars['ulf#_channel_id'] = self.vim.channel_id

    def _on_attach(self, view: VimView) -> None:
        debug('attached buffer %d' % view.buffer_id())
        self.vim.call('ulf#attach_buffer', view.buffer_id())
        self.vim.vars['ulf#attached_bufnr'] = view.buffer_id()
        self.vim.command('doautocmd <nomodeline> User ULFAttachBuffer')
        del self.vim.vars['ulf#attached_bufnr']

    def _on_detach(self, view: VimView) -> None:
        pass

    @pynvim.function('ULF_handle_did_open', sync=True, eval='expand("<abuf>")')
    def _on_did_open(self, args, bufnr):
        debug('buffer {} opened'.format(bufnr))
        view = self.window.view_for_buffer(int(bufnr))
        self.manager.activate_view(view)
        self.documents.handle_did_open(view)

    @pynvim.function('ULF_handle_will_save', eval='expand("<abuf>")')
    def _on_will_save(self, args, bufnr):
        view = self.window.view_for_buffer(int(bufnr))
        self.documents.handle_will_save(view, reason=1)

    @pynvim.function('ULF_handle_did_save', eval='expand("<abuf>")')
    def _on_did_save(self, args, bufnr):
        view = self.window.view_for_buffer(int(bufnr))
        self.documents.handle_did_save(view)

    @pynvim.function('ULF_handle_did_change', eval='expand("<abuf>")')
    def _on_did_change(self, args, bufnr):
        view = self.window.view_for_buffer(int(bufnr))
        self.documents.handle_did_change(view)

    @pynvim.function('ULF_handle_did_close', eval='expand("<abuf>")')
    def _on_did_close(self, args, bufnr):
        if not self.vim.api.buf_is_loaded(int(bufnr)):
            return

        view = self.window.view_for_buffer(int(bufnr), False)
        debug("Event: did_close - %s - %s" % (bufnr, view))

        if view:
            self.manager.handle_view_closed(view)
            self.documents.handle_did_close(view)
            self.window.close_view(int(bufnr))

    @pynvim.function('ULF_handle_leave', sync=True)
    def _on_vimleave(self, args):
        self.window.valid = False
        self.manager.end_sessions()

    @pynvim.function('ULF_hover')
    def hover(self, args):
        self.send_request(RequestMethod.HOVER, args)

    @pynvim.function('ULF_signature_help')
    def signature_help(self, args):
        self.send_request(RequestMethod.SIGNATURE_HELP, args)

    @pynvim.function('ULF_goto_definition')
    def goto_definition(self, args):
        self.send_request(RequestMethod.DEFINITION, args)

    @pynvim.function('ULF_goto_type_definition')
    def goto_type_definition(self, args):
        self.send_request(RequestMethod.TYPE_DEFINITION, args)

    @pynvim.function('ULF_goto_implementation')
    def goto_implementation(self, args):
        self.send_request(RequestMethod.IMPLEMENTATION, args)

    @pynvim.function('ULF_workspace_symbol')
    def workspace_symbol(self, args):
        self.send_request(RequestMethod.WORKSPACE_SYMBOL, args)

    @pynvim.function('ULF_references')
    def references(self, args):
        self.send_request(RequestMethod.REFERENCES, args)

    @pynvim.function('ULF_rename')
    def rename(self, args):
        self.send_request(RequestMethod.RENAME, args)

    @pynvim.function('ULF_code_actions')
    def code_actions(self, args: List[Dict[str, Any]] = [{}]):
        self.send_request(RequestMethod.CODE_ACTION, args)

    @pynvim.function('ULF_complete')
    def complete(self, args: List[Dict[str, Any]] = [{}]):
        self.send_request(RequestMethod.COMPLETION, args)

    @pynvim.function('ULF_complete_sync', sync=True)
    def complete_sync(self, args: List[Dict[str, Any]] = [{}]):
        self.send_request(RequestMethod.COMPLETION, args, sync=True)

    @pynvim.function('ULF_show_diagnostics')
    def show_diagnostics(self, args):
        bufnr = args[0]
        view = self.window.view_for_buffer(int(bufnr))
        if view:
            self.diagnostics_presenter.show_all(view.file_name())

    @pynvim.function('ULF_send_request')
    def send_request(self, method, args, sync=False):
        helper = RequestHelper.for_method(method)
        if helper:
            instance = helper(self, self.vim)
            if sync:
                instance.run_sync(*args)
            else:
                instance.run(*args)
        else:
            debug('No helper found for method={}'.format(method))

    def _update_configs(self) -> None:
        configs = self.vim.vars.get('ulf#configs', {})
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


_HELPERS: Dict[str, Any] = {}


def _helper_exists(cls, lsp_method) -> bool:
    helpers = _HELPERS.get(lsp_method)
    cls_name = ".".join([cls.__module__, cls.__name__])
    for helper in helpers:
        helper_name = ".".join([helper.__module__, helper.__name__])
        if helper_name == cls_name:
            return True
    return False


def import_helpers(runtime: str) -> None:
    paths: List[str] = runtime.split('\n')

    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        module_name = 'ulf.helper.%s' % name
        spec = importlib.util.spec_from_file_location(module_name, p)

        if spec:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)


class RequestHelper(metaclass=abc.ABCMeta):
    _registry = {}

    def __init__(self, ulf: ULF, vim: Nvim):
        self.ulf = ulf
        self.vim = vim

    def current_view(self) -> VimView:
        bufnr = self.vim.current.buffer.number
        return self.ulf.window.view_for_buffer(int(bufnr))

    def cursor_point(self) -> Point:
        cursor = self.vim.current.window.cursor
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

    def run(self, *args, **kwargs):
        raise NotImplementedError()

    def run_sync(self, *args, **kwargs):
        raise NotImplementedError()

    @classmethod
    def for_method(cls, method: str):
        helper = cls._registry.get(method)
        return helper

    def __init_subclass__(cls, method=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._registry[method] = cls


class ClientHelper(metaclass=abc.ABCMeta):
    _registry_by_name: Dict[str, Any] = {}
    _registry_generic: List[Any] = []

    def __init__(self, ulf, vim):
        self.ulf = ulf
        self.vim = vim

    def setup(self, config_name: str, window: VimWindow, view: VimView) -> bool:
        return True

    def on_initialized(self, config_name: str, window: VimWindow, client: Client) -> None:
        pass

    @classmethod
    def for_name(cls, config_name: str = None) -> 'List[ClientHelper]':
        try:
            return [cls._registry_by_name[config_name]] + cls._registry_generic
        except KeyError:
            return cls._registry_generic

    @classmethod
    def instance(cls, ulf, vim, *args, **kwargs) -> 'ClientHelper':
        try:
            return cls._instance
        except AttributeError:
            cls._instance = cls(ulf, vim, *args, **kwargs)
            return cls._instance

    def __init_subclass__(cls, config_name=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if config_name:
            cls._registry_by_name[config_name] = cls
        else:
            cls._registry_generic.append(cls)


class ClientHelperDispacher(object):

    def __init__(self, ulf, vim):
        self.ulf = ulf
        self.vim = vim

    def _helper_instances(self, config_name) -> List[ClientHelper]:
        return list(map(lambda cls: cls.instance(self.ulf, self.vim),
                        ClientHelper.for_name(config_name)))

    def setup(self, config_name: str, window: VimWindow, view: VimView) -> bool:
        helpers = self._helper_instances(config_name)
        return all(helper.setup(config_name, window, view)
                   for helper in helpers) if helpers else True

    def on_initialized(self, config_name: str, window: VimWindow, client: Client) -> None:
        helpers = self._helper_instances(config_name)
        for helper in helpers:
            helper.on_initialized(config_name, window, client)


class DiagnosticsHelper(ClientHelper):

    def on_initialized(self, config_name: str, window: VimWindow, client: Client) -> None:
        client.on_notification(
            "textDocument/publishDiagnostics",
            lambda params: self.ulf.diagnostics.receive(config_name, params))
