from .goto import GotoHandler
from .core.protocol import Request
from .core.logging import debug
from .core.views import text_document_position_params


class ReferencesHandler(GotoHandler):

    def __init__(self, ulf, vim):
        super().__init__(ulf, vim, kind='references')

    def run(self) -> None:
        view = self.current_view()
        point = self.cursor_point()

        session = self.ulf.session_for_view(view)
        if session and session.has_capability('referencesProvider'):
            params = text_document_position_params(view, point)
            params['context'] = {'includeDeclaration': False}
            session.client.send_request(
                Request.references(params),
                self._handle_response,
                lambda res: debug(res))
