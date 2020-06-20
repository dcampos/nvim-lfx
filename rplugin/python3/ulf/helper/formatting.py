from ..ulf import RequestHelper
from ..core.protocol import RequestMethod
from ..core.logging import debug
from ..core.views import text_document_range_formatting, text_document_formatting
from ..core.edit import parse_text_edit


class DocumentFormattingHelper(RequestHelper, method=RequestMethod.FORMATTING):

    def run(self) -> None:
        view = self.current_view()
        session = self.ulf.session_for_view(view, 'documentFormattingProvider')
        if session is not None:
            session.client.send_request(
                text_document_formatting(view),
                self.handle_response,
                lambda res: debug(res))
        else:
            self.ulf.editor.error_message('Not available!')

    def handle_response(self, response):
        if not response:
            return

        edits = list(parse_text_edit(change) for change in response) if response else []

        self.vim.async_call(lambda: self.ulf.editor.apply_document_edits(
            self.current_view().file_name(), edits))


class DocumentRangeFormattingHelper(DocumentFormattingHelper,
                                    method=RequestMethod.RANGE_FORMATTING):

    def run(self) -> None:
        view = self.current_view()
        selection = self.selection_range()
        session = self.ulf.session_for_view(view, 'documentRangeFormattingProvider')
        if session is not None:
            session.client.send_request(
                text_document_range_formatting(view, selection),
                self.handle_response,
                lambda res: debug(res))
        else:
            self.ulf.editor.error_message('Not available!')
