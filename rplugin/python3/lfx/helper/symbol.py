from ..lfx import RequestHelper
from ..core.protocol import RequestMethod, Point
# from ..core.logging import debug
from ..core.url import uri_to_filename
from ..core.typing import Dict, Any
from ..core.views import text_document_identifier


class DocumentSymbolHelper(RequestHelper, method=RequestMethod.DOCUMENT_SYMBOL, capability='documentSymbolProvider'):

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        return {"textDocument": text_document_identifier(view)}

    def handle_response(self, response) -> None:
        pass  # No implementation for now


class WorkspaceSymbolHelper(RequestHelper, method=RequestMethod.WORKSPACE_SYMBOL, capability='workspaceSymbolProvider'):

    def params(self, options) -> Dict[str, Any]:
        return {'query': options.get('query')}

    def handle_response(self, response) -> None:
        if not response:
            self.lfx.editor.error_message('No symbol found!')
            return

        self.vim.async_call(self._display_locations, response)

    def _display_locations(self, response):
        def parse_info(location) -> Dict:
            file_name = uri_to_filename(location['location']['uri'])
            point = Point.from_lsp(location['location']['range']['start'])
            row, col = self.lfx.editor.adjust_from_lsp(file_name, point.row, point.col)
            row += 1
            col += 1
            return {'filename': file_name,
                    'lnum': row, 'col': col, 'text': location['name']}

        locations = list(map(parse_info, response))

        if len(locations) == 1:
            location = locations[0]
            self.lfx.editor.goto(location['filename'], location['lnum'], location['col'])
        else:
            self.vim.call('setqflist', locations)
            self.vim.command('botright copen')
