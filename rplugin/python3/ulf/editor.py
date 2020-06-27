from .core.typing import Callable, List, Optional, Any, Dict, Iterator
from .core.editor import Editor, Window, View
from .core.sessions import Session
from .core.logging import debug
from .core.diagnostics import Diagnostic
from .core.edit import parse_range
from .util import to_byte_index, to_char_index
import os
import re

from pynvim import Nvim
from pynvim.api import Buffer
from threading import Timer

TAG = '[ULF]'


class VimEditor(Editor):
    def __init__(self, ulf) -> None:
        self.ulf = ulf
        self.vim: Nvim = self.ulf.vim
        self.window = VimWindow(self)
        # TODO: transfer these to the helpers once they are single instances
        self.symbol_hl_id = self.vim.new_highlight_source()
        self.color_hl_id = self.vim.new_highlight_source()

    def set_timeout_async(self, f: Callable, timeout_ms: int = 0) -> None:
        timer = Timer(timeout_ms / 1000, lambda: self.vim.async_call(f))
        timer.start()

    def message_dialog(self, message: str) -> None:
        self.status_message(message)

    def status_message(self, message: str) -> None:
        self.vim.async_call(self.vim.out_write, "{} {}\n".format(TAG, message))

    def error_message(self, message: str) -> None:
        self.vim.async_call(self.vim.err_write, "{} {}\n".format(TAG, message))

    def ok_cancel_dialog(self, msg: str, ok_title: str = None) -> str:
        raise NotImplementedError()

    def expand_variables(self, value, variables) -> str:
        return value

    def windows(self):
        return [self.window]

    def active_window(self):
        return self.window

    def show_menu(self, options: List[str], handler: Callable[[int], None], message: str = None) -> None:
        def show_and_handle():
            items = ['{}. {}'.format(i+1, o) for i, o in enumerate(options)]
            if message:
                items.insert(0, message)
            res = self.vim.funcs.inputlist(items) - 1
            handler(res)

        if options:
            self.vim.async_call(show_and_handle)

    def adjust_from_lsp(self, file_path, row, col):
        """Adjust LSP point to byte index (0-based)"""
        bufnr = self.vim.funcs.bufnr(file_path, True)
        if not self.vim.api.buf_is_loaded(bufnr):
            self.vim.funcs.bufload(bufnr)
        line_text = self.vim.api.buf_get_lines(bufnr, row, row+1, False)[0]
        byte_index = to_byte_index(line_text, col)
        col = byte_index
        row = row
        return row, col

    def adjust_to_lsp(self, file_path, row, col):
        """Adjust byte index (0-based) to char index (0-based)"""
        bufnr = self.vim.funcs.bufnr(file_path, True)
        if not self.vim.api.buf_is_loaded(bufnr):
            self.vim.funcs.bufload(bufnr)
        line_text = self.vim.api.buf_get_lines(bufnr, row, row+1, False)[0]
        char_index = to_char_index(line_text, col)
        col = char_index
        row = row
        return row, col

    def apply_workspace_edits(self, changes):
        for file_path, changelist in changes.items():
            self.apply_document_edits(file_path, changelist)

    def apply_document_edits(self, file_path, changes):
        bufnr = self.vim.funcs.bufnr(file_path, True)

        if not self.vim.api.buf_is_loaded(bufnr):
            self.vim.funcs.bufload(bufnr)
            self.vim.api.buf_set_option(bufnr, 'buflisted', True)

        buffer_lines = self.vim.buffers[bufnr][:]

        debug('applying changes to %s' % file_path)

        for change in reversed(changes):
            buffer_lines = self.apply_edit(buffer_lines, change)

        # buffer_lines = self.vim.api.buf_get_lines(bufnr, 0, -1, False)
        # self.vim.funcs.writefile(buffer_lines, file_path)

        self.vim.api.buf_set_lines(bufnr, 0, -1, False, buffer_lines)
        # self.vim.api.buf_set_option(bufnr, 'modified', False)

    def apply_edit(self, source_lines, edit) -> None:
        (start_line, start_col), (end_line, end_col), new_text = edit

        text_before = (source_lines[start_line][:start_col]
                       if start_line < len(source_lines) else '')
        text_after = (source_lines[end_line][end_col:]
                      if end_line < len(source_lines) else '')

        new_text = text_before + new_text + text_after

        # Not using splitlines in order to keep empty ending lines
        new_lines = re.split(r'(?:\r?\n)', new_text)

        source_lines[start_line:end_line + 1] = new_lines

        return source_lines

    def test_changes(self, changelist, old_content, new_content):
        changes = []
        for change in changelist:
            if 'range' in change:
                start = parse_range(change['range']['start'])
                end = parse_range(change['range']['end'])
                new_text = change['text']
                changes.append([start, end, new_text])
            else:
                return

        debug(changes)

        lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        for change in changes:
            lines = self.apply_edit(lines, change)

        # debug('\n'.join(lines))
        # debug('\n'.join(new_lines))
        assert lines == new_lines


class VimWindow(Window):
    ID = 1

    def __init__(self, editor: VimEditor):
        self.editor = editor
        self.vim: Nvim = editor.vim
        self.valid = True
        self._open_views = {}

    def view_for_buffer(self, bufnr: int, create: bool = True) -> 'VimView':
        if create:
            try:
                return self._open_views[bufnr]
            except KeyError:
                view = VimView(self, bufnr)
                self._open_views[bufnr] = view
                return view
        else:
            return self._open_views.get(bufnr)

    def close_view(self, bufnr: int) -> None:
        try:
            del self._open_views[bufnr]
        except KeyError:
            pass

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
        self.editor: VimEditor = window.editor
        self.buffer: Buffer = self.vim.buffers[bufnr]
        self._bufnr = bufnr
        self._file_name = self.vim.funcs.fnamemodify(self.buffer.name, ':p')
        self._language_id = self.buffer.options['filetype']

    def id(self) -> int:
        return self._bufnr

    def file_name(self):
        return self._file_name

    def buffer_id(self):
        return self._bufnr

    def change_count(self) -> int:
        return self.buffer.vars['changedtick']

    def window(self) -> Window:
        return self._window

    def language_id(self) -> str:
        return self._language_id

    def set_status(self, key: str, status: str) -> None:
        pass

    def entire_content(self) -> str:
        content = '\n'.join(self.buffer[:])
        eol = self.buffer.options['eol']
        if eol and content:
            content += '\n'
        return content

    def tab_size(self) -> int:
        return self.buffer.options['shiftwidth']

    def translate_tabs_to_spaces(self) -> bool:
        return self.buffer.options['expandtab']

    def is_valid(self):
        return self.vim.api.buf_is_valid(self._bufnr)

    def available_sessions(self, capability: str = None) -> Iterator[Session]:
        yield from self.editor.ulf.sessions_for_view(self, capability)

    def diagnostics(self) -> Dict[str, List[Diagnostic]]:
        diagnostics = self.editor.ulf.diagnostics.get()
        return diagnostics.get(self.file_name(), {})

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
