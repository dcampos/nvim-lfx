from ..ulf import RequestHelper
from ..core.protocol import Request, RequestMethod
from ..core.logging import debug
from ..core.signature_help import create_signature_help
from ..core.views import text_document_position_params


class SignatureHelpHelper(RequestHelper, method=RequestMethod.SIGNATURE_HELP):

    def run(self) -> None:
        bufnr = self.vim.current.buffer.number
        view = self.current_view()
        point = self.cursor_point()
        self.ulf.documents.purge_changes(view)
        session = self.ulf.session_for_view(view, 'signatureHelpProvider')
        if session is not None:
            session.client.send_request(
                Request.signatureHelp(text_document_position_params(view, point)),
                self._handle_response,
                lambda res: debug(res))
        else:
            debug('Session is none for buffer={}'.format(bufnr))

    def _handle_response(self, response):
        if response is None:
            return
        signature_help = create_signature_help(response)
        if signature_help is None:
            return
        active_signature = signature_help.active_signature()
        self.vim.async_call(self.vim.command, 'echo ""')
        cmd = []
        for i, parameter in enumerate(active_signature.parameters):
            if i == signature_help._active_parameter_index:
                cmd.append('echohl WarningMsg | echon "{}" | echohl None |'.format(parameter.label))
            else:
                cmd.append('echon "{}" |'.format(parameter.label))
        self.vim.async_call(self.vim.command,
                            'echo "" | echon "(" | {} echon ")"'.format(' echon ", " | '.join(cmd)))
