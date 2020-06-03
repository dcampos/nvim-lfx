import difflib
import re

from .typing import List, Optional, Dict, Any
from .logging import debug
from .protocol import ContentChange, Point, Range


def parse_diff(fromfile: str, tofile: str) -> List[ContentChange]:
    if not fromfile or not tofile:
        return [ContentChange(tofile)]

    lines1 = fromfile.splitlines(True)
    lines2 = tofile.splitlines(True)
    diff = list(difflib.unified_diff(lines1, lines2, fromfile='a', tofile='b', n=0))

    debug(diff)

    changes = []

    for line in diff:
        if line.startswith('@@'):
            m = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n', line)
            line1, size1, line2, size2 = [int(g) for g in m.groups('1')]
            # lines_from = lines1[line1 - 1:line1 + size1 - 1]
            lines_to = lines2[line2 - 1:line2 + size2 - 1]
            text = ''.join(lines_to)
            if size1 == 0:
                line1 += 1
            start = Point(line1 - 1, 0)
            end = Point(line1 + size1 - 1, 0)
            range_ = Range(start, end)
            change = ContentChange(text, range_)
            changes.append(change)
            debug(change.to_lsp())

    return changes


def content_changes(content_old: Optional[str] = '',
                    content_new: Optional[str] = '') -> List[Dict[str, Any]]:
    return [c.to_lsp() for c in reversed(parse_diff(content_old, content_new))]
