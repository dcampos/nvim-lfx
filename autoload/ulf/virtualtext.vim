"=============================================================================
" File: autoload/ulf/virtualtext.vim
" License: MIT
" Description: virtual text functions.
"=============================================================================

function! ulf#virtualtext#place_lightbulb(expr, line) abort
    call nvim_buf_set_virtual_text(a:expr, s:ns_id, a:line, [["\U1F4A1", 'NONE']], {})
endfunction

function! ulf#virtualtext#clear_lightbulbs(expr) abort
    call nvim_buf_clear_namespace(a:expr, s:ns_id, 0, -1)
endfunction

function! s:initialize() abort
    let s:ns_id = nvim_create_namespace('')
endfunction

call s:initialize()
