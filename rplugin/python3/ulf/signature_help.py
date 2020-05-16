from .ulf import ULFHandler
from .core.protocol import Request
from .core.logging import debug
from .core.signature_help import create_signature_help
from .core.views import text_document_position_params
from .editor import VimView
from .core.protocol import Point


class SignatureHelpHandler(ULFHandler):

    def run(self) -> None:
        bufnr = self.vim.current.buffer.number
        cursor = self.vim.current.window.cursor
        view = VimView(self.ulf.window, bufnr)
        self.ulf.documents.purge_changes(view)
        point = Point(cursor[0] - 1, cursor[1])
        session = self.ulf._session_for_buffer(bufnr)
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

