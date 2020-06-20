from ..ulf import RequestHelper
from ..core.views import text_document_position_params
from ..core.protocol import Request, RequestMethod
from ..core.logging import debug
from ..core.url import uri_to_filename
from ..core.typing import Tuple, List
from ..core.protocol import Point
from pynvim import Nvim


class GotoDefinitionHelper(RequestHelper, method=RequestMethod.DEFINITION):

    def __init__(self, ulf, _vim: Nvim):
        super().__init__(ulf, _vim)
        self.goto_kind = 'definition'

    def run(self) -> None:
        view = self.current_view()
        point = self.cursor_point()
        capability = self.goto_kind + 'Provider'
        session = self.ulf.session_for_view(view, capability)
        if session:
            request_type = getattr(Request, self.goto_kind)
            session.client.send_request(
                request_type(text_document_position_params(view, point)),
                self.handle_response,
                lambda res: debug(res))
        else:
            debug('Session is none for buffer={} and {}'.format(view.buffer_id(), capability))
            self.ulf.editor.error_message("Not available!")

    def handle_response(self, response) -> None:
        def process_response_list(responses: list) -> List[Tuple[str, str, Tuple[int, int]]]:
            locations = [process_response(x) for x in responses]

            if len(locations) == 1:
                file_path, _, pos = locations[0]
                self._goto(file_path, pos[0], pos[1])
            else:
                self._display_locations(locations)
                pass

        def process_response(response: dict) -> Tuple[str, str, Tuple[int, int]]:
            if "targetUri" in response:
                # TODO: Do something clever with originSelectionRange and targetRange.
                file_path = uri_to_filename(response["targetUri"])
                start = Point.from_lsp(response["targetSelectionRange"]["start"])
            else:
                file_path = uri_to_filename(response["uri"])
                start = Point.from_lsp(response["range"]["start"])
            row, col = self.ulf.editor.adjust_from_lsp(file_path, start.row, start.col)
            row += 1
            col += 1
            file_path_and_row_col = "{}:{}:{}".format(file_path, row, col)
            return file_path, file_path_and_row_col, (row, col)

        if not response:
            return

        if isinstance(response, dict):
            response = [response]

        self.vim.async_call(process_response_list, response)

        # for item in response:
        #     debug('{}: {}:{}'.format(item['uri'], item['range']['start'], item['range']['end']))

    def _goto(self, file, line, col=1):
        bufnr = self.vim.funcs.bufnr(file, True)
        self.vim.command("normal m'")
        self.vim.command('buffer %d' % bufnr)
        self.vim.funcs.cursor(line, col)

    def _display_locations(self, locations):
        def to_item(location):
            file_name, _, (row, col) = location
            return {'filename': file_name, 'lnum': row, 'col': col}

        items = list(map(to_item, locations))

        self.vim.call('setqflist', items)
        self.vim.command('copen')


class GotoTypeDefinitionHelper(GotoDefinitionHelper, method=RequestMethod.TYPE_DEFINITION):

    def __init__(self, ulf, _vim: Nvim):
        super().__init__(ulf, _vim)
        self.goto_kind = 'typeDefinition'


class GotoImplementationHelper(GotoDefinitionHelper, method=RequestMethod.IMPLEMENTATION):

    def __init__(self, ulf, _vim: Nvim):
        super().__init__(ulf, _vim)
        self.goto_kind = 'implementation'


class ReferencesHelper(GotoDefinitionHelper, method=RequestMethod.REFERENCES):

    def __init__(self, ulf, vim):
        super().__init__(ulf, vim)
        self.goto_kind = 'references'

    def run(self) -> None:
        view = self.current_view()
        point = self.cursor_point()

        session = self.ulf.session_for_view(view)
        if session and session.has_capability('referencesProvider'):
            params = text_document_position_params(view, point)
            params['context'] = {'includeDeclaration': False}
            session.client.send_request(
                Request.references(params),
                self.handle_response,
                lambda res: debug(res))
