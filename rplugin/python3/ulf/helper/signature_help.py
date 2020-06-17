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
                self.handle_response,
                lambda res: debug(res))
        else:
            debug('Session is none for buffer={}'.format(bufnr))

    def handle_response(self, response):
        if response is None:
            return
        signature_help = create_signature_help(response)
        if signature_help is None:
            return
        active_signature = signature_help.active_signature()
        self.vim.async_call(self.vim.command, 'echo ""')
        cmd = 'echo "" | '
        if active_signature.parameters and signature_help._active_parameter_index in range(
                0, len(active_signature.parameters)):
            parameter = active_signature.parameters[signature_help._active_parameter_index]
            start, end = parameter.range
            cmd += 'echon "{}" | '.format(active_signature.label[:start])
            cmd += 'echohl WarningMsg | echon "{}" | echohl None | '.format(parameter.label)
            cmd += 'echon "{}"'.format(active_signature.label[end:])
        else:
            cmd += 'echon "{}"'.format(active_signature.label)
        self.vim.async_call(self.vim.command, cmd)
