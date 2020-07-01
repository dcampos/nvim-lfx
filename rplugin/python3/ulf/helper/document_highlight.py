from ..ulf import RequestHelper
from ..core.protocol import RequestMethod, Range
# from ..core.logging import debug
from ..core.typing import Dict, Any
from ..core.views import text_document_position_params


class DocumentHighlightHelper(RequestHelper,
                              method=RequestMethod.DOCUMENT_HIGHLIGHT,
                              capability='documentHighlightProvider'):

    def __init__(self, ulf, vim, *args, **kwargs) -> None:
        super().__init__(ulf, vim)
        self.symbol_hl_id = self.vim.api.create_namespace('ulf#document_highlight#ns_id')

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        point = self.cursor_point()
        return text_document_position_params(view, point)

    def handle_response(self, response):
        highlights = []
        for item in response:
            range_ = Range.from_lsp(item['range'])
            start = range_.start
            end = range_.end
            highlights.append([start, end])
        self.vim.async_call(self._add_highlights, highlights)

    def _add_highlights(self, highlights):
        self.vim.current.buffer.clear_highlight(src_id=self.symbol_hl_id)
        hl_group = self.vim.vars.get('ulf#highlight#document_highlight', 'Search')
        for (start, end) in highlights:
            file_path = self.current_view().file_name()
            start_row, start_col = self.ulf.editor.adjust_from_lsp(file_path, start.row, start.col)
            end_row, end_col = self.ulf.editor.adjust_from_lsp(file_path, end.row, end.col)
            self.vim.current.buffer.add_highlight(hl_group, start_row, start_col, end_col,
                                                  src_id=self.symbol_hl_id)
