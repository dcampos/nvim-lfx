from ..ulf import RequestHelper
from ..core.protocol import Request, RequestMethod, Range
from ..core.logging import debug
from ..core.views import text_document_position_params


class DocumentHighlightHelper(RequestHelper, method=RequestMethod.DOCUMENT_HIGHLIGHT):

    def run(self) -> None:
        view = self.current_view()
        point = self.cursor_point()
        session = self.ulf.session_for_view(view, 'documentHighlightProvider')
        if session is not None:
            session.client.send_request(
                Request.documentHighlight(text_document_position_params(view, point)),
                self.handle_response,
                lambda res: debug(res))
        else:
            self.ulf.editor.error_message('Not available!')

    def handle_response(self, response):
        highlights = []
        for item in response:
            range_ = Range.from_lsp(item['range'])
            start = range_.start
            end = range_.end
            highlights.append([start, end])
        self.vim.async_call(self._add_highlights, highlights)

    def _add_highlights(self, highlights):
        self.vim.current.buffer.clear_highlight(src_id=self.ulf.editor.hl_id)
        hl_group = self.vim.vars.get('ulf#highlight#document_highlight', 'Search')
        for (start, end) in highlights:
            file_path = self.current_view().file_name()
            start_row, start_col = self.ulf.editor.adjust_from_lsp(file_path, start.row, start.col)
            end_row, end_col = self.ulf.editor.adjust_from_lsp(file_path, end.row, end.col)
            self.vim.current.buffer.add_highlight(hl_group, start_row, start_col, end_col,
                                                  src_id=self.ulf.editor.hl_id)
