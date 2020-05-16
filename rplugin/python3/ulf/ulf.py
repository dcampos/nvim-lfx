import importlib
import os.path
import pynvim
import abc
from pynvim import Nvim

from .core.typing import Dict, List, Callable, Optional, Any
from .core.settings import settings, ClientConfigs, ClientConfig
from .core.sessions import create_session, Session
from .core.protocol import WorkspaceFolder, Point
from .core.logging import set_log_file, set_debug_logging, set_exception_logging, debug
from .core.workspace import ProjectFolders
from .core.diagnostics import DiagnosticsStorage
from .documents import VimDocumentHandler, VimConfigManager
from .editor import VimEditor, VimWindow, VimView
from .context import ContextManager, DummyLanguageHandlerDispatcher
from .diagnostics import DiagnosticsPresenter

# from .hover import HoverHandler
# from .signature_help import SignatureHelpHandler
# from .goto import GotoHandler
# from .workspace_symbol import WorkspaceSymbolHandler
# from .completion import CompletionHandler

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
        self.client_configs = ClientConfigs() # type: ClientConfigs
        self._update_configs()
        self.editor = VimEditor(self)
        self.window = VimWindow(self.editor)
        self.config_manager = VimConfigManager(self.window, self.client_configs.all)
        self.documents = VimDocumentHandler(self.editor, self.settings, None, self.window,
                                            self.config_manager)

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

        self.diagnostics_presenter = DiagnosticsPresenter(self.window, self.documents)

        self.manager = ContextManager(
            self.window,
            ProjectFolders(self.window),
            self.settings,
            self.config_manager,
            self.documents,
            DiagnosticsStorage(self.diagnostics_presenter),
            start_session,
            self.editor,
            DummyLanguageHandlerDispatcher())

        import_handlers(self.vim.funcs.globpath(self.vim.options['runtimepath'],
                                                'rplugin/python3/ulf/handler/*.py'))

        self.vim.vars['ulf#_channel_id'] = self.vim.channel_id

    @pynvim.autocmd('BufEnter,BufWinEnter,FileType', pattern='*', eval='expand("<abuf>")', sync=True)
    def _on_did_open(self, bufnr: int):
        debug('buffer {} opened'.format(bufnr))
        view = VimView(self.window, int(bufnr))
        self.manager.activate_view(view)
        self.documents.handle_did_open(view)
        # self.vim.request('nvim_buf_attach',
        #                   int(bufnr),
        #                   True,
        #                   {})

    @pynvim.autocmd('BufWritePre', pattern='*', eval='expand("<abuf>")')
    def _on_will_save(self, bufnr: int):
        view = VimView(self.window, int(bufnr))
        self.documents.handle_will_save(view, reason=1)

    @pynvim.autocmd('BufWritePost', pattern='*', eval='expand("<abuf>")')
    def _on_did_save(self, bufnr: int):
        view = VimView(self.window, int(bufnr))
        self.documents.handle_did_save(view)

    @pynvim.autocmd('TextChanged,TextChangedP,TextChangedI', pattern='*', eval='expand("<abuf>")')
    def _on_did_change(self, bufnr: int):
        view = VimView(self.window, int(bufnr))
        self.documents.handle_did_change(view)

    @pynvim.autocmd('BufWipeout,BufDelete,BufUnload', pattern='*', eval='expand("<abuf>")')
    def _on_did_close(self, bufnr: int):
        view = VimView(self.window, int(bufnr))
        self.manager.handle_view_closed(view)
        self.documents.handle_did_close(view)

    @pynvim.autocmd('VimLeavePre', pattern='*', sync=True)
    def _on_vimleave(self):
        self.window.valid = False;

    @pynvim.command('ULFHover')
    def hover(self):
        from .hover import HoverHandler
        handler = HoverHandler(self, self.vim)
        handler.run()

    @pynvim.command('ULFSignatureHelp')
    def signature_help(self):
        from .signature_help import SignatureHelpHandler
        handler = SignatureHelpHandler(self, self.vim)
        handler.run()

    @pynvim.command('ULFGotoDefinition')
    def goto_definition(self):
        from .goto import GotoHandler
        handler = GotoHandler(self, self.vim)
        handler.run()

    @pynvim.command('ULFWorkspaceSymbol', nargs='1')
    def workspace_symbol(self, args):
        from .workspace_symbol import WorkspaceSymbolHandler
        handler = WorkspaceSymbolHandler(self, self.vim)
        handler.run(args[0])

    @pynvim.function('ULF_complete')
    def complete(self, args: List[Dict[str, Any]] = [{}]):
        from .completion import CompletionHandler
        params = args[0]
        handler = CompletionHandler(self, self.vim, params)
        handler.run()

    @pynvim.function('ULF_complete_sync', sync=True)
    def complete_sync(self, args: List[Dict[str, Any]] = [{}]):
        from .completion import CompletionHandler
        params = args[0]
        handler = CompletionHandler(self, self.vim, params, sync=True)
        handler.run()

    @pynvim.function('ULF_show_diagnostics')
    def show_diagnostics(self, args):
        bufnr = args[0] or -1
        view = VimView(self.window, int(bufnr))
        if view:
            self.diagnostics_presenter.show_all(view.file_name())

    @pynvim.function('ULF_send_request')
    def send_request(self, args):
        method, *params = args
        handler = HANDLERS.get(method)
        if handler:
            instance = handler(self, self.vim)
            instance.run()
        else:
            debug('no handler found for method={}'.format(method))

    # @pynvim.rpc_export('nvim_buf_lines_event')
    # def _buf_lines_event(self, *args):
    #     debug('------> lines event: {}'.format(args))

    # @pynvim.rpc_export('nvim_buf_detach_event')
    # def _buf_detach_event(self, *args):
    #     debug('------> detach event: {}'.format(args))

    # @pynvim.rpc_export('nvim_buf_changedtick_event')
    # def _buf_changedtick_event(self, *args):
    #     debug('------> changedtick event: {}'.format(args))

    def _update_configs(self) -> None:
        configs = self.vim.vars.get('ulf#configs', {})
        for config in configs.values():
            config['languages'] = []
            for filetype in config.get('filetypes', []):
                # TODO: convert appropriately
                config['languages'].append({'languageId' : filetype})
        self.client_configs.update({'clients': configs})

    def _session_for_buffer(self, bufnr) -> Session:
        view = VimView(self.window, bufnr)
        for config in self.client_configs.all:
            for language in config.languages:
                if language.id == view.language_id():
                    return self.manager.get_session(config.name, view.file_name())
        return None

    def _error_handler(self, result):
        self.vim.async_call(self.vim.err_write, result)

# import functools

HANDLERS = {} # type: List[str]

def request_handler(method):
    def request_decorator(func):
        HANDLERS[method] = func
        return func
    return request_decorator


def import_handlers(runtime: str) -> None:
    paths: List[str] = runtime.split('\n')
    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        module_name = 'ulf.handler.%s' % name
        spec = importlib.util.spec_from_file_location(module_name, p)
        if spec:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)


class ULFHandler(metaclass=abc.ABCMeta):

    def __init__(self, ulf: ULF, vim: Nvim):
        self.ulf = ulf
        self.vim = vim

    def current_view(self) -> VimView:
        bufnr = self.vim.current.buffer.number
        return VimView(self.ulf.window, bufnr)

    def cursor_point(self) -> Point:
        cursor = self.vim.current.window.cursor
        return Point(cursor[0] - 1, cursor[1])

    def run(self):
        raise NotImplementedError()

