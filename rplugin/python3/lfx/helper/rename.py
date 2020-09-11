from ..lfx import RequestHelper, LFX
from ..core.views import text_document_position_params
from ..core.protocol import RequestMethod
from ..core.logging import debug
from ..core.edit import parse_workspace_edit
from ..core.typing import Dict, Any
# from ..core.logging import debug
from pynvim import Nvim


class PrepareRenameHelper(RequestHelper,
                          method=RequestMethod.PREPARE_RENAME,
                          capability='renameProvider'):

    def is_enabled(self) -> bool:
        view = self.current_view()
        session = self.lfx.session_for_view(view, self.capability)
        provider = session.get_capability(self.capability)
        return provider and type(provider) == dict and provider.get('prepareProvider', False)

    def params(self, options):
        view = self.current_view()
        point = self.cursor_point()
        return text_document_position_params(view, point)

    def handle_response(self, response):
        debug(response)


class RenameHelper(RequestHelper, method=RequestMethod.RENAME, capability='renameProvider'):

    def __init__(self, lfx: LFX, vim: Nvim) -> None:
        super().__init__(lfx, vim)

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        point = self.cursor_point()
        params = text_document_position_params(view, point)
        params['newName'] = options.get('new_name')
        return params

    def handle_response(self, response):
        changes = parse_workspace_edit(response)
        # debug(f'changes: {changes}')

        self.vim.async_call(self.lfx.editor.apply_workspace_edits, changes)
