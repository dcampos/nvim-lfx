from threading import Timer


def to_byte_index(text, idx):
    return len(text[:idx].encode()) if idx else 0


def to_char_index(text, idx):
    return len(text.encode()[:idx].decode()) if idx else 0


def debounce(wait, call_id, func):
    callers = {}

    def call_func():
        try:
            callers.pop(call_id)
            func()
        except KeyError:
            pass

    try:
        caller = callers[call_id]
        caller.cancel()
    except KeyError:
        pass

    caller = Timer(wait, call_func)
    caller.start()
    callers[call_id] = caller
