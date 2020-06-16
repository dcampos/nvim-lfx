from ..ulf import RequestHelper, ULF
from ..core.views import text_document_position_params
from ..core.protocol import Request, RequestMethod
from ..core.logging import debug
from ..core.edit import parse_workspace_edit
from pynvim import Nvim


class RenameHelper(RequestHelper, method=RequestMethod.RENAME):

    def __init__(self, ulf: ULF, vim: Nvim) -> None:
        super().__init__(ulf, vim)

    def run(self, new_name: str) -> None:
        view = self.current_view()
        point = self.cursor_point()
        session = self.ulf.session_for_view(view, 'renameProvider')
        if session:
            params = text_document_position_params(view, point)
            params['newName'] = new_name
            session.client.send_request(
                Request.rename(params),
                self.handle_response,
                lambda res: debug(res))

    def handle_response(self, response):
        changes = parse_workspace_edit(response)
        # debug(json.dumps(changes))

        self.vim.async_call(self.ulf.editor.apply_workspace_edits, changes)
