from .ulf import ULFHandler
from .core.protocol import Request, Point
from .core.logging import debug
from .core.url import uri_to_filename
from .core.typing import Dict, List

class WorkspaceSymbolHandler(ULFHandler):

    def run(self, query: str) -> None:
        bufnr = self.vim.current.buffer.number
        session = self.ulf._session_for_buffer(bufnr)
        if session and session.has_capability('workspaceSymbolProvider'):
            session.client.send_request(
                Request.workspaceSymbol({'query': query}),
                self._handle_response,
                lambda res: debug(res))
        else:
            debug('Session is none for buffer={}'.format(bufnr))


    def _handle_response(self, response) -> None:
        def _parse_info(location) -> Dict:
            point = Point.from_lsp(location['location']['range']['start'])
            return { 'filename': uri_to_filename(location['location']['uri']),
                    'lnum': point.row + 1, 'col': point.col + 1, 'text': location['name'] }

        if not response:
            self.ulf.editor.error_message('No symbol found!')
            return

        locations = list(map(_parse_info, response))

        self.vim.async_call(self._display_locations, locations)


    def _goto(self, file, line, col=1):
        self.vim.command('edit {}'.format(file))
        self.vim.command('call cursor({}, {})'.format(line, col))


    def _display_locations(self, locations: List):
        self.vim.call('setqflist', locations)
        self.vim.command('copen')
