from .ulf import ULFHandler, ULF
from .core.views import text_document_position_params
from .core.protocol import Request
from .core.logging import debug
from .core.edit import parse_workspace_edit
from pynvim import Nvim


class RenameHandler(ULFHandler):

    def __init__(self, ulf: ULF, vim: Nvim, new_name: str) -> None:
        super().__init__(ulf, vim)
        self._new_name = new_name

    def run(self) -> None:
        view = self.current_view()
        point = self.cursor_point()
        session = self.ulf.session_for_view(view)
        if session and session.has_capability('renameProvider'):
            params = text_document_position_params(view, point)
            params['newName'] = self._new_name
            session.client.send_request(
                Request.rename(params),
                self.handle_response,
                lambda res: debug(res))

    def handle_response(self, response):
        changes = parse_workspace_edit(response)
        # debug(json.dumps(changes))

        self.vim.async_call(self.ulf.editor.apply_workspace_edits, changes)
