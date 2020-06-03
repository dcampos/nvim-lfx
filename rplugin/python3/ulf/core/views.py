from .editor import View, Settings
from .protocol import Point, Range, Notification, Request
from .typing import Dict, Any
from .url import filename_to_uri
from .diff import content_changes


class MissingFilenameError(Exception):

    def __init__(self, view_id: int) -> None:
        super().__init__("View {} has no filename".format(view_id))
        self.view_id = view_id


def uri_from_view(view: View) -> str:
    file_name = view.file_name()
    if file_name:
        return filename_to_uri(file_name)
    raise MissingFilenameError(view.id())


def text_document_identifier(view: View) -> Dict[str, Any]:
    return {"uri": uri_from_view(view)}


def entire_content(view: View) -> str:
    return view.entire_content()


def text_document_item(view: View, language_id: str) -> Dict[str, Any]:
    return {
        "uri": uri_from_view(view),
        "languageId": language_id,
        "version": view.change_count(),
        "text": entire_content(view)
    }


def versioned_text_document_identifier(view: View) -> Dict[str, Any]:
    return {"uri": uri_from_view(view), "version": view.change_count()}


def text_document_position_params(view: View, point: Point) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(view), "position": point.to_lsp()}


def did_open_text_document_params(view: View, language_id: str) -> Dict[str, Any]:
    return {"textDocument": text_document_item(view, language_id)}


def did_change_text_document_params(view: View, previous_content: str = '') -> Dict[str, Any]:
    return {
        "textDocument": versioned_text_document_identifier(view),
        "contentChanges": content_changes(previous_content, view.entire_content())
    }


def will_save_text_document_params(view: View, reason: int) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(view), "reason": reason}


def did_save_text_document_params(view: View, include_text: bool) -> Dict[str, Any]:
    result = {"textDocument": text_document_identifier(view)}  # type: Dict[str, Any]
    if include_text:
        result["text"] = entire_content(view)
    return result


def did_close_text_document_params(view: View) -> Dict[str, Any]:
    return {"textDocument": text_document_identifier(view)}


def did_open(view: View, language_id: str) -> Notification:
    return Notification.didOpen(did_open_text_document_params(view, language_id))


def did_change(view: View, previous_content: str=None) -> Notification:
    return Notification.didChange(did_change_text_document_params(view, previous_content))


def will_save(view: View, reason: int) -> Notification:
    return Notification.willSave(will_save_text_document_params(view, reason))


def will_save_wait_until(view: View, reason: int) -> Request:
    return Request.willSaveWaitUntil(will_save_text_document_params(view, reason))


def did_save(view: View, include_text: bool) -> Notification:
    return Notification.didSave(did_save_text_document_params(view, include_text))


def did_close(view: View) -> Notification:
    return Notification.didClose(did_close_text_document_params(view))


def formatting_options(view: View) -> Dict[str, Any]:
    return {
        "tabSize": view.tab_size(),
        "insertSpaces": view.translate_tabs_to_spaces()
    }


def text_document_formatting(view: View) -> Request:
    return Request.formatting({
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings())
    })


def text_document_range_formatting(view: View, range: Range) -> Request:
    return Request.rangeFormatting({
        "textDocument": text_document_identifier(view),
        "options": formatting_options(view.settings()),
        "range": range
    })
