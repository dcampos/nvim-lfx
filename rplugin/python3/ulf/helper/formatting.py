from ..ulf import RequestHelper
from ..core.typing import Any, Dict
from ..core.protocol import RequestMethod
# from ..core.logging import debug
from ..core.views import text_document_range_formatting, text_document_formatting
from ..core.edit import parse_text_edit


class DocumentFormattingHelper(RequestHelper, method=RequestMethod.FORMATTING):

    def __init__(self, ulf, _vim, capability='documentFormattingProvider'):
        super().__init__(ulf, _vim, capability)

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        selection = self.selection_range()
        return text_document_range_formatting(view, selection)

    def handle_response(self, response):
        if not response:
            return

        edits = list(parse_text_edit(change) for change in response) if response else []

        self.vim.async_call(lambda: self.ulf.editor.apply_document_edits(
            self.current_view().file_name(), edits))


class DocumentRangeFormattingHelper(DocumentFormattingHelper,
                                    method=RequestMethod.RANGE_FORMATTING):

    def __init__(self, ulf, _vim):
        super().__init__(ulf, _vim, 'documentRangeFormattingProvider')

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        return text_document_formatting(view)
