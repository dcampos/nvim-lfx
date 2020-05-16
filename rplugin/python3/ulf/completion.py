from .ulf import ULFHandler
from .core.typing import Dict, Any
from .core.protocol import Request
from .core.logging import debug
from .core.views import text_document_position_params
from .core.completion import parse_completion_response, completion_item_kind_names


class CompletionHandler(ULFHandler):

    def __init__(self, ulf, vim, params: Dict[str, Any], sync=False):
        super().__init__(ulf, vim)
        self.params = params
        self.sync = sync

    def run(self) -> None:
        view = self.current_view()
        point = self.cursor_point()
        session = self.ulf._session_for_buffer(view.buffer_id())
        if session and session.has_capability('completionProvider'):
            # Ensure all changes are committed
            self.ulf.documents.purge_changes(view)
            if self.sync:
                session.client.execute_request(
                    Request.complete(text_document_position_params(view, point)),
                    self.handle_response,
                    lambda res: debug(res))
            else:
                session.client.send_request(
                    Request.complete(text_document_position_params(view, point)),
                    self.handle_response,
                    lambda res: debug(res))

    def handle_response(self, response) -> None:
        if not response:
            return
        items, incomplete = parse_completion_response(response)
        debug('completion items: {}'.format(items))
        if self.sync:
            self.process_completion_items(items)
        else:
            self.vim.async_call(self.process_completion_items, items)

    def process_completion_items(self, items) -> Dict[str, Any]:
        self.matches = []

        base = self.params.get('base')

        for item in items:
            if base and not item['label'].startswith(base):
                continue

            self.matches.append({
                'word': item.get('insertText') or item['label'],
                'abbr': item['label'],
                'menu': item.get('detail', ''),
                'kind': completion_item_kind_names[item.get('kind')],
                'icase': 1,
                'dup': 1,
                'empty': 1,
            })

        try:
            target = self.params.get('target')
            self.vim.vars[target] = self.matches
        except:
            pass

        try:
            callback = self.params.get('callback')
            include_results = self.params.get('include_results', True)

            if include_results:
                self.vim.call(callback, self.matches)
            else:
                self.vim.call(callback)
        except:
            pass
