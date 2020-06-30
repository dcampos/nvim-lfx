from ..ulf import RequestHelper
from ..core.typing import Any, Dict
from ..core.protocol import RequestMethod
# from ..core.logging import debug
from ..core.signature_help import create_signature_help
from ..core.views import text_document_position_params


class SignatureHelpHelper(RequestHelper, method=RequestMethod.SIGNATURE_HELP, capability='signatureHelpProvider'):

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        point = self.cursor_point()
        return text_document_position_params(view, point)

    def handle_response(self, response):
        self.vim.command('echo ""')
        if response is None:
            return
        signature_help = create_signature_help(response)
        if signature_help is None:
            return
        active_signature = signature_help.active_signature()
        cmd = 'echo "" | '
        pre, label, post = '', '', ''
        if active_signature.parameters and signature_help._active_parameter_index in range(
                0, len(active_signature.parameters)):
            parameter = active_signature.parameters[signature_help._active_parameter_index]
            start, end = parameter.range
            pre = active_signature.label[:start]
            label = parameter.label
            post = active_signature.label[end:]
            # cmd += 'echon "{}" | '.format(active_signature.label[:start].replace('"', '\\"'))
            # cmd += 'echohl WarningMsg | echon "{}" | echohl None | '.format(
            #     parameter.label.replace('"', '\\"'))
            # cmd += 'echon "{}"'.format(active_signature.label[end:].replace('"', '\\"'))
        else:
            cmd += 'echon "{}"'.format(active_signature.label.replace('"', '\\"'))
            pre = active_signature.label

        if self.vim.vars.get('ulf#signature_help#use_echo'):
            cmd += 'echon "{}" | '.format(pre.replace('"', '\\"'))
            cmd += 'echohl WarningMsg | echon "{}" | echohl None | '.format(
                 label.replace('"', '\\"'))
            cmd += 'echon "{}"'.format(post.replace('"', '\\"'))
            self.vim.command(cmd)
        else:
            content = '{}***{}***{}'.format(pre, label, post)
            self.vim.call('ulf#show_popup', [content], True, True)
