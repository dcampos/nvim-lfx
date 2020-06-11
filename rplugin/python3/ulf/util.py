def to_byte_index(text, idx):
    return len(text[:idx].encode()) if idx else 0


def to_char_index(text, idx):
    return len(text.encode()[:idx].decode()) if idx else 0
