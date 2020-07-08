"=============================================================================
" File: autoload/ulf.vim
" License: MIT
" Description: autoload'able functions for ULF.
"=============================================================================

let g:ulf#completion_results = []

function! ulf#enable() abort
    augroup ulf
        autocmd!
        autocmd BufEnter,BufWinEnter,FileType * silent! call ULF_handle_did_open() 
        autocmd BufWipeout,BufDelete,BufUnload * silent! call ULF_handle_did_close()
        autocmd VimLeavePre * silent! call ULF_handle_leave() 
    augroup END

    command! ULFHover call ULF_hover()
    command! ULFSignatureHelp call ULF_signature_help({}, v:false, 0.2)
    command! ULFGotoDefinition call ULF_goto_definition()
    command! ULFGotoTypeDefinition call ULF_goto_type_definition()
    command! ULFGotoImplementation call ULF_goto_implementation()
    command! ULFGotoDeclaration call ULF_goto_declaration()
    command! -nargs=1 -complete=customlist,<sid>complete_symbols
                \ ULFWorkspaceSymbol call ULF_workspace_symbol({'query': <q-args>})
    command! ULFReferences call ULF_references()
    command! ULFDocumentHighlight call ULF_document_highlight()
    command! -nargs=? ULFRename call s:request_rename(<q-args>)
    command! ULFCodeActions call ULF_code_actions({'visual': v:false})
    command! ULFCodeActionsVisual call ULF_code_actions({'visual': v:true})
    command! ULFFormat call ULF_format()
    command! ULFFormatRange call ULF_format_range()

    hi default ULFActiveParameter gui=bold,underline
endfunction

function! s:complete_symbols(arglead, line, pos) abort
    let target = 'ulf#workspace_symbol#results'
    call ULF_workspace_symbol({'query': a:arglead, 'target': target}, v:true)
    let results = get(g:, target, [])
    map(results, 'get(v:val, "name")')
    return results
endfunction

function! s:request_rename(new_name) abort
    unlet! g:ulf#prepare_rename#response

    if empty(a:new_name)
        let l:new_name = ''
        call ULF_prepare_rename({'target': 'ulf#prepare_rename#response'}, v:true)
        if exists('g:ulf#prepare_rename#response')
            let response = g:ulf#prepare_rename#response
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
        call ULF_rename({'new_name': l:new_name})
    endif
endfunction

function! ulf#attach_buffer(bufnr) abort
    augroup ulf_buffer
        execute 'autocmd! * <buffer=' . a:bufnr . '>'
        execute 'autocmd BufWritePre <buffer=' . a:bufnr . '> call ULF_handle_will_save()'
        execute 'autocmd BufWritePost <buffer=' . a:bufnr . '> call ULF_handle_did_save()'
        execute 'autocmd TextChanged,TextChangedP,TextChangedI <buffer=' . a:bufnr
                    \ . '> call ULF_handle_did_change()'
        execute 'autocmd CompleteDone <buffer=' . a:bufnr
                    \ . '> call s:handle_complete_done()'
        execute 'autocmd CompleteChanged <buffer=' . a:bufnr
                    \ . '> call s:handle_complete_changed(v:event)'
        execute 'autocmd CursorMoved,InsertEnter <buffer=' . a:bufnr
                    \ . '> call s:close_popup()'
    augroup END
endfunction

function! ulf#omni(findstart, base) abort
    if a:findstart
        return s:find_start()
    endif

    let col = strchars(s:get_text_to_cursor() . a:base)
    call ULF_complete_sync({
                \ 'target': 'ulf#completion_results',
                \ 'process_response': v:true,
                \ 'base': a:base,
                \ 'col': col
                \ }, v:true)
    let results = get(g:, 'ulf#completion_results', [])
    return results
endfunction

function! ulf#complete() abort
    call ULF_complete({'callback': 'ulf#completion_callback', 'process_response': v:true})
    return ''
endfunction

function! ulf#complete_sync() abort
    call ULF_complete_sync({'target': 'ulf#completion_results', 'process_response': v:true}, v:true)
    let results = get(g:, 'ulf#completion_results', [])
    call ulf#completion_callback(results)
    return ''
endfunction

function! ulf#completion_callback(items) abort
    if type(a:items) !=# type(v:null)
        let match_start = s:find_start() + 1
        call complete(match_start, a:items)
    endif
endfunction

function! ulf#show_popup(content, opts) abort
    call s:close_popup()
    let content = a:content
    if empty(content) || content == [''] | return | endif
    let popup = ulf#popup#new(a:content, extend({
                \ 'floating': 1,
                \ 'enter': v:false,
                \ }, a:opts))
    call popup.open()
    let b:__ulf_popup = popup
endfunction

function! s:close_popup() abort
    call ulf#popup#close_current_popup()
endfunction

function! s:handle_complete_done() abort
    unlet! b:__ulf_pmenu_info
    call ULF_handle_complete_done()
endfunction

function! s:handle_complete_changed(event) abort
    let b:__ulf_pmenu_info = {
                \ 'width': a:event.width,
                \ 'height': a:event.height,
                \ 'col': a:event.col,
                \ 'row': a:event.row
                \ }
    if exists('b:__ulf_popup')
        call timer_start(1, {->b:__ulf_popup.update()})
    endif
    call s:resolve_completion(a:event.completed_item)
endfunction

function! s:resolve_completion(completed_item) abort
    unlet! g:ulf#completion#_resolved_item
    let user_data = get(a:completed_item, 'user_data', {})
    if type(user_data) !=# v:t_dict
        silent! let user_data = json_decode(user_data)
    endif
    if type(user_data) !=# v:t_dict
        return
    endif
    let lspitem = get(user_data, 'lspitem')
    if !empty(lspitem)
        call ULF_resolve_completion({'target': 'ulf#completion#_resolved_item',
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
