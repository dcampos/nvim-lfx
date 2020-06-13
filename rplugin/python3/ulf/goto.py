from .ulf import ULFHandler
from .core.views import text_document_position_params
from .core.protocol import Request
from .core.logging import debug
from .core.url import uri_to_filename
from .core.typing import Tuple, List
from .core.protocol import Point
from .util import to_byte_index
from pynvim import Nvim


class GotoHandler(ULFHandler):

    def __init__(self, ulf, vim: Nvim, kind='definition'):
        super().__init__(ulf, vim)
        self.goto_kind = kind

    def run(self) -> None:
        view = self.current_view()
        point = self.cursor_point()
        capability = self.goto_kind + 'Provider'
        session = self.ulf.session_for_view(view, capability)
        if session:
            request_type = getattr(Request, self.goto_kind)
            session.client.send_request(
                request_type(text_document_position_params(view, point)),
                self._handle_response,
                lambda res: debug(res))
        else:
            debug('Session is none for buffer={} and {}'.format(view.buffer_id(), capability))
            self.ulf.editor.error_message("Not available!")

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

    def _adjust_lsp_col(self, file_path, row, col):
        """Adjust LSP point to byte index"""
        bufnr = self.vim.funcs.bufnr(file_path, True)
        if not self.vim.api.buf_is_loaded(bufnr):
            self.vim.funcs.bufload(bufnr)
        debug("{}:{},{}, bufnr={}".format(file_path, row, col, bufnr))
        line_text = self.vim.api.buf_get_lines(bufnr, row - 1, row, False)[0]
        byte_index = to_byte_index(line_text, col - 1)
        col = byte_index + 1
        return col

    def _goto(self, file, line, col=1):
        bufnr = self.vim.funcs.bufnr(file, True)
        col = self._adjust_lsp_col(file, line, col)
        self.vim.command("normal m'")
        self.vim.command('buffer %d' % bufnr)
        self.vim.funcs.cursor(line, col)

    def _display_locations(self, locations):
        def to_item(location):
            file_name, _, (row, col) = location
            col = self._adjust_lsp_col(file_name, row, col)
            return {'filename': file_name, 'lnum': row, 'col': col}

        items = list(map(to_item, locations))

        self.vim.call('setqflist', items)
        self.vim.command('copen')
