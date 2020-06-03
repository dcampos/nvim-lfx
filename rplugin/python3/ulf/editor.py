from .core.typing import Callable, List, Optional, Any, Dict
from .core.editor import Editor, Window, View
from .core.logging import debug
import os

from pynvim import Nvim
from pynvim.api import Buffer
from threading import Timer

TAG = '[LSP]'


class VimEditor(Editor):
    def __init__(self, ulf) -> None:
        self.ulf = ulf
        self.vim: Nvim = self.ulf.vim
        self.window = VimWindow(self)

    def set_timeout_async(self, f: Callable, timeout_ms: int = 0) -> None:
        timer = Timer(timeout_ms / 1000, lambda: self.vim.async_call(f))
        timer.start()

    def message_dialog(self, message: str) -> None:
        self.status_message(message)

    def status_message(self, message: str) -> None:
        self.vim.async_call(self.vim.out_write, "{} {}\n".format(TAG, message))

    def ok_cancel_dialog(self, msg: str, ok_title: str = None) -> str:
        raise NotImplementedError()

    def expand_variables(self, value, variables) -> str:
        return value

    def windows(self):
        return [self.window]

    def active_window(self):
        return self.window

    def show_message_request(self, source, message_type, message, titles, on_result):
        def input():
            result = self.vim.funcs.inputlist(titles)
            self.vim.async_call(on_result, result)
        self.vim.async_call(input)


class VimWindow(Window):
    ID = 1

    def __init__(self, editor: VimEditor):
        self.editor = editor
        self.vim: Nvim = editor.vim
        self.valid = True

    def id(self) -> int:
        return self.ID

    def is_valid(self) -> bool:
        return self.valid

    def folders(self) -> List[str]:
        return [self.active_view().find_root()]

    def find_open_file(self, path: str) -> Optional[View]:
        bufnr = self.vim.funcs.bufnr(path)
        return VimView(self, bufnr)

    def active_view(self) -> Optional[View]:
        bufnr = self.vim.current.buffer.number
        return VimView(self, bufnr)

    def status_message(self, msg: str) -> None:
        self.editor.status_message(msg)

    def views(self) -> List[View]:
        return [View(b.number) for b in self.vim.list_bufs()
                if self.vim.api.buf_is_loaded(b)]

    def run_command(self, command_name: str, command_args: Dict[str, Any]) -> None:
        raise NotImplementedError()

    def extract_variables(self) -> Dict:
        return {}


class VimView(View):
    def __init__(self, window: VimWindow, bufnr):
        self._window = window
        self.vim: Nvim = window.vim
        self.buffer: Buffer = self.vim.buffers[bufnr]

    def id(self) -> int:
        return self.buffer.number

    def file_name(self):
        return self.vim.funcs.fnamemodify(self.buffer.name, ':p')

    def buffer_id(self):
        return self.buffer.number

    def change_count(self) -> int:
        return self.buffer.vars['changedtick']

    def window(self) -> Window:
        return self._window

    def language_id(self) -> str:
        return self.buffer.options['filetype']

    def set_status(self, key: str, status: str) -> None:
        pass

    def entire_content(self) -> str:
        content = '\n'.join(self.vim.current.buffer[:])
        eol = self.buffer.options['eol']
        if eol and content:
            content += '\n'
        return content

    def tab_size(self) -> int:
        return self.buffer.options['shiftwidth']

    def translate_tabs_to_spaces(self) -> bool:
        return self.buffer.options['expandtab']

    def find_root(self) -> str:
        patterns = (self._window.editor.ulf.root_patterns.get('*') +
                    self._window.editor.ulf.root_patterns.get(self.language_id(), []))
        head, tail = os.path.split(self.file_name())
        found = head
        while tail != '':
            for lookup in patterns:
                lookup = os.path.join(head, lookup)
                if os.path.exists(lookup):
                    found = head
                    break
            head, tail = os.path.split(head)
        _, dirname = os.path.split(found)
        return found
