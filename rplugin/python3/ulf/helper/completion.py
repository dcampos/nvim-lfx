from ..ulf import RequestHelper
from ..core.typing import Dict, Any
from ..core.protocol import RequestMethod
# from ..core.logging import debug
from ..core.views import text_document_position_params
from ..core.completion import parse_completion_response, completion_item_kind_names


class CompletionHelper(RequestHelper, method=RequestMethod.COMPLETION):

    def __init__(self, ulf, vim):
        super().__init__(ulf, vim, 'completionProvider')

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

        for item in items:
            if base and not item['label'].startswith(base):
                continue

            matches.append({
                'word': item.get('insertText') or item['label'],
                'abbr': item['label'],
                'menu': item.get('detail', ''),
                'kind': completion_item_kind_names[item.get('kind')],
                'icase': 1,
                'dup': 1,
                'empty': 1,
            })

        return matches
