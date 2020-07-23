from ..ulf import RequestHelper
from ..core.views import text_document_position_params
from ..core.protocol import Request, RequestMethod
from ..core.logging import debug
from ..core.url import uri_to_filename
from ..core.typing import Tuple, List, Any, Dict
from ..core.protocol import Point
from pynvim import Nvim


class GotoDefinitionHelper(RequestHelper, method=RequestMethod.DEFINITION, capability='definitionProvider'):

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        point = self.cursor_point()
        return text_document_position_params(view, point)

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
        self.vim.command('botright copen')


class GotoTypeDefinitionHelper(GotoDefinitionHelper, method=RequestMethod.TYPE_DEFINITION, capability='typeDefinition'):
    pass


class GotoImplementationHelper(GotoDefinitionHelper, method=RequestMethod.IMPLEMENTATION,
                               capability='implementationProvider'):
    pass


class GotoDeclarationHelper(GotoDefinitionHelper, method=RequestMethod.DECLARATION, capability='declarationProvider'):
    pass


class ReferencesHelper(GotoDefinitionHelper, method=RequestMethod.REFERENCES, capability='referencesProvider'):

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        point = self.cursor_point()
        params = text_document_position_params(view, point)
        params['context'] = {'includeDeclaration': False}
        return params
