"=============================================================================
" File: autoload/lfx/sign.vim
" License: MIT
" Description:
"=============================================================================

function! lfx#sign#place_lightbulb(expr, line) abort
    call sign_place(0, 'LFXLightbulb', 'LFXLightbulb', a:expr,
                \ {'lnum': a:line, 'priority': 100})
endfunction

function! lfx#sign#clear_lightbulbs() abort
    call sign_unplace('LFXLightbulb')
endfunction

function! s:initialize() abort
    call sign_define('LFXLightbulb', {'text': "\U1F4A1", 'texthl': 'LFXLightbulbSign'})
    highlight default link LFXLightbulbSign SignColumn
endfunction

call s:initialize()
