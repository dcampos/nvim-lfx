"=============================================================================
" File: autoload/lfx.vim
" License: MIT
" Description: autoload'able functions for LFX.
"=============================================================================

let g:lfx#completion_results = []

function! lfx#enable() abort
    augroup lfx
        autocmd!
        autocmd BufEnter,BufWinEnter,FileType * silent! call LFX_handle_did_open() 
        autocmd BufWipeout,BufDelete,BufUnload * silent! call LFX_handle_did_close()
        autocmd VimLeavePre * silent! call LFX_handle_leave() 
    augroup END

    command! LFXHover call LFX_hover()
    command! LFXSignatureHelp call LFX_signature_help({}, v:false, 0.2)
    command! LFXGotoDefinition call LFX_goto_definition()
    command! LFXGotoTypeDefinition call LFX_goto_type_definition()
    command! LFXGotoImplementation call LFX_goto_implementation()
    command! LFXGotoDeclaration call LFX_goto_declaration()
    command! -nargs=1 -complete=customlist,<sid>complete_symbols
                \ LFXWorkspaceSymbol call LFX_workspace_symbol({'query': <q-args>})
    command! LFXReferences call LFX_references()
    command! LFXDocumentHighlight call LFX_document_highlight()
    command! -nargs=? LFXRename call s:request_rename(<q-args>)
    command! LFXCodeActions call LFX_code_actions({'visual': v:false})
    command! LFXCodeActionsVisual call LFX_code_actions({'visual': v:true})
    command! LFXFormat call LFX_format()
    command! LFXFormatRange call LFX_format_range()

    hi default LFXActiveParameter gui=bold,underline
endfunction

function! s:complete_symbols(arglead, line, pos) abort
    let target = 'lfx#workspace_symbol#results'
    call LFX_workspace_symbol({'query': a:arglead, 'target': target}, v:true)
    let results = get(g:, target, [])
    let candidates = map(results, 'get(v:val, "name")')
    return candidates
endfunction

function! s:request_rename(new_name) abort
    unlet! g:lfx#prepare_rename#response

    if empty(a:new_name)
        let l:new_name = ''
        call LFX_prepare_rename({'target': 'lfx#prepare_rename#response'}, v:true)
        if exists('g:lfx#prepare_rename#response')
            let response = g:lfx#prepare_rename#response
            if type(response) == type(v:null)
                echohl WarningMsg | echom 'Rename not possible here!' | echohl None
                return
            elseif type(response) ==# v:t_dict
                if has_key(response, 'placeholder')
                    let l:new_name = response.placeholder
                elseif has_key(response, 'start')
                    let startchar = response['start'].character
                    let endchar = response['end'].character
                    let line = getline('.')
                    let l:new_name = strcharpart(line, startchar, endchar - startchar)
                endif
            endif
        endif
        let l:new_name = input('New name: ', l:new_name)
    else
        let l:new_name = a:new_name
    endif

    if l:new_name !=# ''
        call LFX_rename({'new_name': l:new_name})
    endif
endfunction

function! lfx#attach_buffer(bufnr) abort
    augroup lfx_buffer
        execute 'autocmd! * <buffer=' . a:bufnr . '>'
        execute 'autocmd BufWritePre <buffer=' . a:bufnr . '> call LFX_handle_will_save()'
        execute 'autocmd BufWritePost <buffer=' . a:bufnr . '> call LFX_handle_did_save()'
        execute 'autocmd TextChanged,TextChangedP,TextChangedI <buffer=' . a:bufnr
                    \ . '> call LFX_handle_did_change()'
        execute 'autocmd CompleteDone <buffer=' . a:bufnr
                    \ . '> call s:handle_complete_done()'
        execute 'autocmd CompleteChanged <buffer=' . a:bufnr
                    \ . '> call s:handle_complete_changed(v:event)'
        execute 'autocmd CursorMoved,InsertEnter <buffer=' . a:bufnr
                    \ . '> call s:close_popup()'
        execute 'autocmd CursorHold <buffer=' . a:bufnr
                    \ . '> call s:fetch_code_actions(v:false)'
        execute 'autocmd CursorMoved <buffer=' . a:bufnr
                    \ . '> call s:fetch_code_actions_visual()'
    augroup END
endfunction

function! lfx#omni(findstart, base) abort
    if a:findstart
        return s:find_start()
    endif

    let col = strchars(s:get_text_to_cursor() . a:base)
    call LFX_complete_sync({
                \ 'target': 'lfx#completion_results',
                \ 'process_response': v:true,
                \ 'base': a:base,
                \ 'col': col
                \ }, v:true)
    let results = get(g:, 'lfx#completion_results', [])
    return results
endfunction

function! lfx#complete() abort
    call LFX_complete({'callback': 'lfx#completion_callback', 'process_response': v:true})
    return ''
endfunction

function! lfx#complete_sync() abort
    call LFX_complete_sync({'target': 'lfx#completion_results', 'process_response': v:true}, v:true)
    let results = get(g:, 'lfx#completion_results', [])
    call lfx#completion_callback(results)
    return ''
endfunction

function! lfx#completion_callback(items) abort
    if type(a:items) !=# type(v:null)
        let match_start = s:find_start() + 1
        call complete(match_start, a:items)
    endif
endfunction

let s:count = 0

function! lfx#code_action_callback(results) abort
    call s:dismiss_code_actions()
    let available = len(filter(a:results, '!empty(v:val)')) > 0
    if available
        call lfx#virtualtext#place_lightbulb(0, line('.') - 1)
    endif
endfunction

function! lfx#show_popup(content, opts) abort
    call s:close_popup()
    let content = a:content
    if empty(content) || content == [''] | return | endif
    let popup = lfx#popup#new(a:content, extend({
                \ 'floating': 1,
                \ 'enter': v:false,
                \ }, a:opts))
    call popup.open()
    let b:__lfx_popup = popup
endfunction

function! s:close_popup() abort
    call lfx#popup#close_current_popup()
endfunction

function! s:fetch_code_actions_visual() abort
    let mode = mode()
    if l:mode =~# '\v\c^%(v)$' || l:mode ==# "\<C-V>"
        " Hack to update visual marks
        execute "normal! \<esc>gv"
        call s:fetch_code_actions(v:true)
    endif
endfunction

function! s:fetch_code_actions(visual) abort
    call LFX_code_actions({
                \ 'callback': 'lfx#code_action_callback',
                \ 'include_results': v:true,
                \ 'visual': a:visual
                \ }, v:false, 0.2)
endfunction

function! s:dismiss_code_actions() abort
    call lfx#virtualtext#clear_lightbulbs(0)
endfunction

function! s:handle_complete_done() abort
    unlet! b:__lfx_pmenu_info
    call LFX_handle_complete_done()
endfunction

function! s:handle_complete_changed(event) abort
    let b:__lfx_pmenu_info = {
                \ 'width': a:event.width,
                \ 'height': a:event.height,
                \ 'col': a:event.col,
                \ 'row': a:event.row
                \ }
    if exists('b:__lfx_popup')
        call timer_start(1, {->b:__lfx_popup.update()})
    endif
    call s:resolve_completion(a:event.completed_item)
endfunction

function! s:resolve_completion(completed_item) abort
    unlet! g:lfx#completion#_resolved_item
    let user_data = get(a:completed_item, 'user_data', {})
    if type(user_data) !=# v:t_dict
        silent! let user_data = json_decode(user_data)
    endif
    if type(user_data) !=# v:t_dict
        return
    endif
    let lspitem = get(user_data, 'lspitem')
    if !empty(lspitem)
        call LFX_resolve_completion({'target': 'lfx#completion#_resolved_item',
                    \ 'completion_item': lspitem})
    endif
endfunction

function! s:find_start() abort
    let line = s:get_text_to_cursor()
    let match_start = match(line, '\k\+$')
    if match_start < 0
        let match_start = col('.') - 1
    endif
    return match_start
endfunction

function! s:get_text_to_cursor() abort
    return getline('.')[:col('.')-1]
endfunction
