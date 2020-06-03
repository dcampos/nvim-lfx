from .editor import VimWindow
from .core.typing import Dict, List, Any
from .core.protocol import DiagnosticSeverity
from .core.diagnostics import Diagnostic, DocumentsState
from .core.logging import debug


diagnostic_severity_names = {
    DiagnosticSeverity.Error: "E",
    DiagnosticSeverity.Warning: "W",
    DiagnosticSeverity.Information: "I",
    DiagnosticSeverity.Hint: "I"
}


class DiagnosticsPresenter(object):

    def __init__(self, window: VimWindow, documents_state: DocumentsState) -> None:
        self._window = window
        self._vim = window.vim
        self._dirty = False
        self._received_diagnostics_after_change = False
        self._diagnostics = {}  # type: Dict[str, Dict[str, List[Diagnostic]]]
        setattr(documents_state, 'changed', self.on_document_changed)
        setattr(documents_state, 'saved', self.on_document_saved)

    def on_document_changed(self) -> None:
        self._received_diagnostics_after_change = False

    def on_document_saved(self) -> None:
        pass

    def update(self, file_path: str, config_name: str, diagnostics: Dict[str, Dict[str, List[Diagnostic]]]) -> None:
        debug("received diagnostics: {}".format(diagnostics));
        self._diagnostics = diagnostics
        self._received_diagnostics_after_change = True

        if not self._window.is_valid():
            debug('ignoring update to closed window')
            return

        # diagnostics = diagnostics.get(file_path, {}).get(config_name, [])

        # self._vim.async_call(self._show_results, file_path, diagnostics)
        self._vim.async_call(self.show_all, file_path)

    def show_all(self, file_path):
        diagnostics = self._diagnostics.get(file_path, {})  # type: Dict[str, List[Diagnostic]]
        if not diagnostics:
            self._show_results(file_path, [])
        else:
            file_diagnostics = []
            for config_diagnostics in diagnostics.values():
                file_diagnostics.extend(config_diagnostics)
            self._show_results(file_path, file_diagnostics)

    def _show_results(self, file_path, diagnostics: List[Diagnostic]):
        view = self._window.find_open_file(file_path)
        bufnr = view.buffer_id()

        loclist = []  # type: List[Dict[str, Any]]

        for diagnostic in diagnostics:
            start = diagnostic.range.start
            end = diagnostic.range.end
            loclist.append({
                'type': diagnostic_severity_names.get(diagnostic.severity, 'E'),
                'text': diagnostic.message,
                'lnum': start.row + 1,
                'col': start.col + 1,
                'end_lnum': end.row + 1,
                'end_col': end.col + 1,
                'bufnr': bufnr
            })

        self._vim.api.buf_set_var(bufnr, 'ulf_diagnostics', loclist)
        self._vim.call('ale#other_source#ShowResults', bufnr, 'ulf', loclist)

    def select(self, direction: int) -> None:
        pass

    def deselect(self) -> None:
        pass
