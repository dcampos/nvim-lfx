import difflib
import re

from .typing import List, Tuple, Optional, Dict, Any
from .logging import debug

class Change(object):
    def __init__(self, range_from, range_to) -> None:
        self.range_from = range_from # type: Tuple[int, int]
        self.range_to = range_to     # type: Tuple[int, int]
        self.lines_from = []         # type: List[str]
        self.lines_to = []           # type: List[str]

    def to_lsp(self) -> Dict[str, Any]:
        from_line = self.range_from[0] - 1
        to_line = self.range_from[1] - 1
        if len(self.lines_from) == 0:
            from_line += 1
            to_line += 1
        return {
            'text': ''.join(self.lines_to),
            'range': {
                'start': {'line': from_line, 'character': 0},
                'end': {'line': to_line, 'character': 0}
            }
        }

    def __repr__(self) -> str:
        return "Change(\n\t{}: {},\n\t{}: {}\n)".format(
            self.range_from, self.lines_from, self.range_to, self.lines_to)


def parse_diff(fromfile: str, tofile: str) -> List[Change]:
    lines1 = fromfile.splitlines(True)
    lines2 = tofile.splitlines(True)
    diff = list(difflib.unified_diff(lines1, lines2, fromfile='a', tofile='b', n=0))

    debug(diff)

    changes = []

    for line in diff:
        if line.startswith('@@'):
            m = re.match('@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n', line)
            line1 = int(m.group(1))
            size1 = int(m.group(2) or 1)
            line2 = int(m.group(3))
            size2 = int(m.group(4) or 1)
            range_from = line1, line1 + size1
            range_to = line2, line2 + size2
            change = Change(range_from, range_to)
            change.lines_from = lines1[line1 - 1:line1 + size1 - 1]
            change.lines_to = lines2[line2 - 1:line2 + size2 - 1]
            changes.append(change)
            debug(change)

    return changes

def content_changes(content_new: str, content_old: Optional[str] = None) -> List[Dict[str, Any]]:
    if not content_old:
        return [{'text': content_new}]
    else:
        return [c.to_lsp() for c in reversed(parse_diff(content_old, content_new))]
