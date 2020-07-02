from ..ulf import RequestHelper
from ..core.typing import Any, Dict, Tuple
from ..core.protocol import RequestMethod
from ..core.logging import debug
from ..core.signature_help import create_signature_help
from ..core.views import text_document_position_params
from ..util import to_byte_index


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
        pre, label, post = '', '', ''
        if active_signature.parameters and signature_help._active_parameter_index in range(
                0, len(active_signature.parameters)):
            parameter = active_signature.parameters[signature_help._active_parameter_index]
            start, end = parameter.range
            pre = active_signature.label[:start]
            label = parameter.label
            post = active_signature.label[end:]
        else:
            pre = active_signature.label

        if self.vim.vars.get('ulf#signature_help#use_echo'):
            cmd = 'echo "" | '
            cmd += 'echon "{}" | '.format(pre.replace('"', '\\"'))
            cmd += 'echohl ULFActiveParameter | echon "{}" | echohl None | '.format(
                 label.replace('"', '\\"'))
            cmd += 'echon "{}"'.format(post.replace('"', '\\"'))
            self.vim.command(cmd)
        else:
            content = '{}{}{}'.format(pre, label, post)
            highlights = []
            if start and end:
                highlights.append(['ULFActiveParameter', 0,
                                   to_byte_index(content, start) + 1,
                                   to_byte_index(content, end) + 1])
            offset = self.calculate_offset(content, start)
            self.vim.call('ulf#show_popup', [content], {'prefer_top': True,
                                                        'offsets': [offset, 0],
                                                        'paddings': [1, 0],
                                                        'highlights': highlights})

    def calculate_offset(self, content: str, start: int) -> int:
        trigger_offset = self._find_last_trigger(content, 0, start)

        offset = -start + (start - 1 - trigger_offset) - 1  # final -1 for padding

        line = self.vim.current.line
        row, col = self.vim.current.window.cursor
        trigger_index = self._find_last_trigger(line, 0, col)

        if trigger_index >= 0:
            offset -= col - trigger_index - 1

        # debug(f'{start}, {trigger_offset}, {trigger_index}, {offset}')

        return offset

    def _find_last_trigger(self, line, start: int = 0, end: int = -1, triggers='(,') -> int:
        return max(line.rfind(c, start, end) for c in triggers)
