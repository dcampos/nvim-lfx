"=============================================================================
" File: autoload/ulf/sign.vim
" License: MIT
" Description:
"=============================================================================

function! ulf#sign#place_lightbulb(expr, line) abort
    call sign_place(0, 'ULFLightbulb', 'ULFLightbulb', a:expr,
                \ {'lnum': a:line, 'priority': 100})
endfunction

function! ulf#sign#clear_lightbulbs() abort
    call sign_unplace('ULFLightbulb')
endfunction

function! s:initialize() abort
    call sign_define('ULFLightbulb', {'text': "\U1F4A1", 'texthl': 'ULFLightbulbSign'})
    highlight default link ULFLightbulbSign SignColumn
endfunction

call s:initialize()
