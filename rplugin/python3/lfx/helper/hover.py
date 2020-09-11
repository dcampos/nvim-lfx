from ..lfx import RequestHelper
from ..core.protocol import Request, RequestMethod
from ..core.logging import debug
from ..core.views import text_document_position_params
from ..core.typing import Dict, Any
from .goto import GotoDefinitionHelper


class HoverHelper(RequestHelper, method=RequestMethod.HOVER, capability='hoverProvider'):

    def __init__(self, lfx, vim):
        super().__init__(lfx, vim)

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        point = self.cursor_point()
        return text_document_position_params(view, point)

    def handle_response(self, response):
        if response is not None:
            contents = response.get('contents')
            filetype: str = 'text'
            if not isinstance(contents, list):
                contents = [contents]
            result = []
            for content in contents:
                if isinstance(content, str):
                    result.append(content)
                elif isinstance(content, dict):
                    if content.get('kind') == 'markdown':
                        filetype = 'markdown'
                    result.append(content.get('value'))
            content = '\n\n'.join(result).split('\n')
            if self.vim.vars.get('lfx#hover#use_echo'):
                self.vim.command('echon "{}"'.format('\n\n'.join(result).replace('"', '\\"')))
            else:
                self.vim.call('lfx#show_popup', content, {'filetype': filetype})
