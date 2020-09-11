from ..lfx import RequestHelper
from ..core.typing import Any, Dict
from ..core.protocol import RequestMethod
# from ..core.logging import debug
from ..core.views import text_document_range_formatting, text_document_formatting
from ..core.edit import parse_text_edit, sort_by_application_order


class DocumentFormattingHelper(RequestHelper, method=RequestMethod.FORMATTING, capability='documentFormattingProvider'):

    def __init__(self, lfx, _vim):
        super().__init__(lfx, _vim)

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        return text_document_formatting(view)

    def handle_response(self, response):
        if not response:
            return

        edits = list(parse_text_edit(change) for change in response) if response else []
        edits = sort_by_application_order(edits)

        self.vim.async_call(lambda: self.lfx.editor.apply_document_edits(
            self.current_view().file_name(), edits))


class DocumentRangeFormattingHelper(DocumentFormattingHelper,
                                    method=RequestMethod.RANGE_FORMATTING,
                                    capability='documentRangeFormattingProvider'):

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        selection = self.selection_range()
        return text_document_range_formatting(view, selection)
