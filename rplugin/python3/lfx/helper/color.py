from ..lfx import RequestHelper
from ..core.protocol import RequestMethod, Range
from ..core.typing import Any, Dict
from ..core.logging import debug
from ..core.views import text_document_identifier


_groups = []


class DocumentColorHelper(RequestHelper, method=RequestMethod.DOCUMENT_COLOR, capability='colorProvider'):

    def __init__(self, lfx, vim, *args, **kwargs) -> None:
        super().__init__(lfx, vim)
        self.color_hl_id = self.vim.api.create_namespace('lfx#document_color#ns_id')

    def params(self, options) -> Dict[str, Any]:
        view = self.current_view()
        return {'textDocument': text_document_identifier(view)}

    def handle_response(self, response) -> None:
        color_infos = response if response else []
        self.vim.async_call(self._add_highlights, color_infos)

    def _add_highlights(self, color_infos) -> None:
        self.vim.current.buffer.clear_highlight(src_id=self.color_hl_id)
        file_path = self.current_view().file_name()
        for color_info in color_infos:
            color = color_info['color']
            red = int(color['red'] * 255)
            green = int(color['green'] * 255)
            blue = int(color['blue'] * 255)
            # alpha = color['alpha']

            bg_color = '{:02x}{:02x}{:02x}'.format(red, green, blue)

            # Find a contrasting foreground color
            luminance = red * 0.2126 + green * 0.7152 + blue * 0.722
            fg_color = 'ffffff' if luminance < 140 else '000000'

            hl_group = 'LFX_color_{}'.format(bg_color)

            if not self.vim.funcs.hlexists(hl_group):
                self.vim.command('highlight! {} guibg=#{} guifg=#{}'.format(hl_group, bg_color, fg_color))
                _groups.append(hl_group)
                debug(_groups)

            range_ = Range.from_lsp(color_info['range'])

            start_row, start_col = self.lfx.editor.adjust_from_lsp(file_path, range_.start.row,
                                                                   range_.start.col)
            end_row, end_col = self.lfx.editor.adjust_from_lsp(file_path, range_.end.row,
                                                               range_.end.col)
            self.vim.current.buffer.add_highlight(hl_group, start_row, start_col, end_col,
                                                  src_id=self.color_hl_id)
