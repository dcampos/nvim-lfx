from ..ulf import RequestHelper, ULF
from ..core.views import text_document_position_params
from ..core.protocol import Request, RequestMethod
from ..core.logging import debug
from ..core.edit import parse_workspace_edit
from ..core.typing import Dict, Any
from pynvim import Nvim


class RenameHelper(RequestHelper, method=RequestMethod.RENAME, capability='renameProvider'):

    def __init__(self, ulf: ULF, vim: Nvim) -> None:
        super().__init__(ulf, vim)

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        point = self.cursor_point()
        params = text_document_position_params(view, point)
        params['newName'] = options.get('new_name')
        return params

    def handle_response(self, response):
        changes = parse_workspace_edit(response)
        # debug(json.dumps(changes))

        self.vim.async_call(self.ulf.editor.apply_workspace_edits, changes)
