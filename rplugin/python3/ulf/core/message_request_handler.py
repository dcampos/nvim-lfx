from .protocol import Response
from .rpc import Client
from .typing import Any, List, Callable
from .editor import View


class MessageRequestHandler():
    def __init__(self, view: View, client: Client, request_id: Any, params: dict, source: str) -> None:
        self.client = client
        self.request_id = request_id
        self.request_sent = False
        self.view = view
        actions = params.get("actions", [])
        self.titles = list(action.get("title") for action in actions)
        self.message = params.get('message', '')
        self.message_type = params.get('type', 4)
        self.source = source

    def _send_user_choice(self, href: int = -1) -> None:
        if not self.request_sent:
            self.request_sent = True
            self.view.hide_popup()
            # when noop; nothing was selected e.g. the user pressed escape
            param = None
            index = int(href)
            if index != -1:
                param = {"title": self.titles[index]}
            response = Response(self.request_id, param)
            self.client.send_response(response)

    def show(self) -> None:
        show_notification(
            self.view,
            self.source,
            self.message_type,
            self.message,
            self.titles,
            self._send_user_choice
        )


def show_notification(view: View, source: str, message_type: int, message: str, titles: List[str],
                      on_result: Callable) -> None:
    # show_message_request(source, message_type, message, titles, on_result)
    view.show_menu(titles, on_result, message)
