let g:ulf#completion_results = []

function! ulf#omni(findstart, base) abort
    if a:findstart
        return s:find_start()
    endif

    call ULF_complete_sync({'target': 'ulf#completion_results', 'base': a:base})
    let results = get(g:, 'ulf#completion_results', [])
    return results
endfunction

function! ulf#complete() abort
    call ULF_complete({'callback': 'ulf#completion_callback'})
    return ''
endfunction

function! ulf#complete_sync() abort
    call ULF_complete_sync({'target': 'ulf#completion_results'})
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
