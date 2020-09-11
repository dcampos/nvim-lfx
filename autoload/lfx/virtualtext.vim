"=============================================================================
" File: autoload/lfx/virtualtext.vim
" License: MIT
" Description: virtual text functions.
"=============================================================================

function! lfx#virtualtext#place_lightbulb(expr, line) abort
    call nvim_buf_set_virtual_text(a:expr, s:ns_id, a:line, [[s:bulb_sign, 'LFXLightbulbVirtual']], {})
endfunction

function! lfx#virtualtext#clear_lightbulbs(expr) abort
    call nvim_buf_clear_namespace(a:expr, s:ns_id, 0, -1)
endfunction

function! s:initialize() abort
    let s:ns_id = nvim_create_namespace('')
    let s:bulb_sign = get(g:, 'lfx#code_actions#sign', "\U1F4A1")
endfunction

call s:initialize()
