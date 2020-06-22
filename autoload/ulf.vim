let g:ulf#completion_results = []

function! ulf#enable() abort
    augroup ulf
        autocmd!
        autocmd BufEnter,BufWinEnter,FileType * call ULF_handle_did_open() 
        autocmd BufWipeout,BufDelete,BufUnload * call ULF_handle_did_close()
        autocmd VimLeavePre * call ULF_handle_leave() 
    augroup END

    command! ULFHover call ULF_hover()
    command! ULFSignatureHelp call ULF_signature_help()
    command! ULFGotoDefinition call ULF_goto_definition()
    command! ULFGotoTypeDefinition call ULF_goto_type_definition()
    command! ULFGotoImplementation call ULF_goto_implementation()
    command! -nargs=1 -complete=customlist,<sid>complete_symbols
                \ ULFWorkspaceSymbol call ULF_workspace_symbol({'query': <q-args>})
    command! ULFReferences call ULF_references()
    command! ULFDocumentHighlight call ULF_document_highlight()
    command! -nargs=? ULFRename call s:request_rename(<q-args>)
    command! ULFCodeActions call ULF_code_actions({'visual': v:false})
    command! ULFCodeActionsVisual call ULF_code_actions({'visual': v:true})
endfunction

function! s:complete_symbols(arglead, line, pos) abort
    let target = 'ulf#workspace_symbol#results'
    call ULF_workspace_symbol({'query': a:arglead, 'target': target}, v:true)
    let results = get(g:, target, [])
    map(results, 'get(v:val, "name")')
    return results
endfunction

function! s:request_rename(new_name) abort
    let l:new_name = a:new_name ==# '' ? input('New name: ') : a:new_name
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
    augroup END
endfunction

function! ulf#omni(findstart, base) abort
    if a:findstart
        return s:find_start()
    endif

    call ULF_complete_sync({'target': 'ulf#completion_results', 'process_response': v:true, 'base': a:base})
    let results = get(g:, 'ulf#completion_results', [])
    return results
endfunction

function! ulf#complete() abort
    call ULF_complete({'callback': 'ulf#completion_callback', 'process_response': v:true})
    return ''
endfunction

function! ulf#complete_sync() abort
    call ULF_complete_sync({'target': 'ulf#completion_results', 'process_response': v:true})
    let results = get(g:, 'ulf#completion_results', [])
    call ulf#completion_callback(results)
    return ''
endfunction

function! ulf#completion_callback(items) abort
    let match_start = s:find_start() + 1
    call complete(match_start, a:items)
endfunction

function! s:find_start() abort
    let line = getline('.')[:col('.')-1]
    let match_start = match(line, '\k\+$')
    if match_start < 0
        let match_start = col('.')
    endif
    return match_start
endfunction
