from .ulf import ULFHandler
from .core.views import text_document_position_params
from .core.protocol import Request
from .core.logging import debug
from .core.url import uri_to_filename
from .core.typing import Tuple, List
from .core.protocol import Point
from .editor import VimView
from pynvim import Nvim

class GotoHandler(ULFHandler):

    def __init__(self, ulf, vim: Nvim, kind='definition'):
        super().__init__(ulf, vim)
        self.goto_kind = kind

    def run(self) -> None:
        bufnr = self.vim.current.buffer.number
        cursor = self.vim.current.window.cursor
        view = VimView(self.ulf.window, bufnr)
        point = Point(cursor[0] - 1, cursor[1])
        session = self.ulf.session_for_view(view)
        if session is not None and session.has_capability(self.goto_kind + 'Provider'):
            request_type = getattr(Request, self.goto_kind)
            session.client.send_request(
                request_type(text_document_position_params(view, point)),
                self._handle_response,
                lambda res: debug(res))
        else:
            debug('Session is none for buffer={}'.format(bufnr))

    def _handle_response(self, response) -> None:
        def process_response_list(responses: list) -> List[Tuple[str, str, Tuple[int, int]]]:
            return [process_response(x) for x in responses]

        def process_response(response: dict) -> Tuple[str, str, Tuple[int, int]]:
            if "targetUri" in response:
                # TODO: Do something clever with originSelectionRange and targetRange.
                file_path = uri_to_filename(response["targetUri"])
                start = Point.from_lsp(response["targetSelectionRange"]["start"])
            else:
                file_path = uri_to_filename(response["uri"])
                start = Point.from_lsp(response["range"]["start"])
            row = start.row + 1
            col = start.col + 1
            file_path_and_row_col = "{}:{}:{}".format(file_path, row, col)
            return file_path, file_path_and_row_col, (row, col)

        if not response:
            return

        if isinstance(response, dict):
            response = [response]

        locations = process_response_list(response)

        if len(locations) == 1:
            file_path, _, pos = locations[0]
            self.vim.async_call(self._goto, file_path, pos[0], pos[1])
        else:
            debug(repr(locations))
            self.vim.async_call(self._display_locations, locations)
            pass

        # for item in response:
        #     debug('{}: {}:{}'.format(item['uri'], item['range']['start'], item['range']['end']))

    def _goto(self, file, line, col=1):
        debug(file)
        self.vim.command('edit {}'.format(file))
        self.vim.command('call cursor({}, {})'.format(line, col))

    def _display_locations(self, locations):
        items = map(lambda item: {'filename': item[0],
                                  'lnum': item[2][0], 'col': item[2][1]}, locations)
        self.vim.call('setqflist', list(items))
        self.vim.command('copen')