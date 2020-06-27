from ..ulf import RequestHelper
from ..core.typing import Dict, Any
from ..core.protocol import RequestMethod
# from ..core.logging import debug
from ..core.views import text_document_position_params
from ..core.completion import parse_completion_response, completion_item_kind_names

import json


class ResolveCompletionHelper(RequestHelper,
                              method=RequestMethod.RESOLVE,
                              capability='completionProvider'):

    def is_enabled(self) -> bool:
        view = self.current_view()
        session = self.ulf.session_for_view(view, self.capability)
        provider = session.get_capability('completionProvider')
        return provider and provider.get('resolveProvider', False)

    def params(self, options):
        return options.get('completion_item')

    def handle_response(self, response):
        pass


class CompletionHelper(RequestHelper, method=RequestMethod.COMPLETION, capability='completionProvider'):

    def __init__(self, ulf, vim):
        super().__init__(ulf, vim)

    def params(self, options):
        view = self.current_view()
        point = self.cursor_point()
        return text_document_position_params(view, point)

    def handle_response(self, response):
        pass

    def process_response(self, response, options) -> Dict[str, Any]:
        if not response:
            return

        items, incomplete = parse_completion_response(response)

        matches = []

        base = options.get('base')

        for rec in items:
            if base and not rec['label'].startswith(base):
                continue

            if 'textEdit' in rec and rec['textEdit'] is not None:
                textEdit = rec['textEdit']
                if textEdit['range']['start'] == textEdit['range']['end']:
                    previous_input = self.vim.vars['deoplete#source#ulf#_prev_input']
                    new_text = textEdit['newText']
                    word = f'{previous_input}{new_text}'
                else:
                    word = textEdit['newText']
            elif rec.get('insertText', ''):
                if rec.get('insertTextFormat', 1) != 1:
                    word = rec.get('entryName', rec.get('label'))
                else:
                    word = rec['insertText']
            else:
                word = rec.get('entryName', rec.get('label'))

            item = {
                'word': word,
                'abbr': rec['label'],
                'dup': 1,
                'icase': 1,
                'empty': 1,
                'user_data': json.dumps({
                    'lspitem': rec
                })
            }

            if isinstance(rec.get('kind'), int):
                item['kind'] = completion_item_kind_names.get(rec['kind'])

            if rec.get('detail'):
                item['menu'] = rec['detail']

            if isinstance(rec.get('documentation'), str):
                item['info'] = rec['documentation']
            elif isinstance(rec.get('documentation'), dict) and 'value' in rec['documentation']:
                item['info'] = rec['documentation']['value']

            if rec.get('insertTextFormat') == 2:
                item['kind'] = 'Snippet'

            matches.append(item)

        return matches
