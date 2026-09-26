"""Bounded display diff over verified snapshot source lines; byte digests stay authoritative."""

import hashlib
from difflib import SequenceMatcher

MAX_FILE_BYTES = 1024 * 1024
MAX_FILE_LINES = 2000
MAX_HUNKS = 200
MAX_DETAIL_FILES = 200
MAX_TOTAL_DETAIL_BYTES = 8 * 1024 * 1024


def needs_lines(entry):
    return (
        entry is not None
        and entry.encoding != "binary"
        and entry.size_bytes <= MAX_FILE_BYTES
        and entry.line_count is not None
        and entry.line_count <= MAX_FILE_LINES
    )


def file_difference(baseline, candidate, baseline_lines, candidate_lines, *, detail_allowed=True):
    """Return a file summary and bounded change blocks with 1-based half-open positions."""
    if baseline is None and candidate is None:
        raise ValueError("A file must exist on at least one side")
    path = (candidate or baseline).path
    if baseline is not None and candidate is not None and baseline.path != candidate.path:
        raise ValueError("Only matching relative paths may be compared")
    change = "added" if baseline is None else "removed" if candidate is None else "changed"
    summary = {
        "file_id": hashlib.sha256(path.encode()).hexdigest(),
        "path": path,
        "change": change,
        "baseline_sha256": baseline.sha256 if baseline else None,
        "candidate_sha256": candidate.sha256 if candidate else None,
        "baseline_encoding": baseline.encoding if baseline else None,
        "candidate_encoding": candidate.encoding if candidate else None,
        "baseline_size_bytes": baseline.size_bytes if baseline else None,
        "candidate_size_bytes": candidate.size_bytes if candidate else None,
        "baseline_line_count": baseline.line_count if baseline else None,
        "candidate_line_count": candidate.line_count if candidate else None,
        "detail_truncated": False,
        "hunk_count": 0,
        "warnings": [],
    }
    reasons = summary["warnings"]
    if not detail_allowed:
        reasons.append("DETAIL_BUDGET")
    if any(entry is not None and entry.encoding == "binary" for entry in (baseline, candidate)):
        reasons.append("BINARY_CONTENT_NOT_DISPLAYABLE")
    if any(
        entry is not None and not needs_lines(entry) and entry.encoding != "binary"
        for entry in (baseline, candidate)
    ):
        reasons.append("FILE_LIMIT")
    if reasons:
        summary["detail_truncated"] = True
        return summary, []
    if (baseline and baseline_lines is None) or (candidate and candidate_lines is None):
        raise ValueError("Small text files require verified source lines")
    left = list(baseline_lines or ())
    right = list(candidate_lines or ())
    if any(line.truncated for line in (*left, *right)):
        reasons.append("LONG_LINE_TRUNCATED")
        summary["detail_truncated"] = True
    if baseline and candidate and [line.text for line in left] == [line.text for line in right]:
        reasons.append("DISPLAY_LINES_EQUAL_RAW_BYTES_DIFFER")
    matcher = SequenceMatcher(
        None, [line.text for line in left], [line.text for line in right], autojunk=False
    )
    hunks = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if len(hunks) >= MAX_HUNKS:
            reasons.append("HUNK_LIMIT")
            summary["detail_truncated"] = True
            break
        hunks.append(
            {
                "tag": tag,
                "baseline_start": i1 + 1,
                "baseline_end": i2 + 1,
                "candidate_start": j1 + 1,
                "candidate_end": j2 + 1,
                "baseline_lines": [
                    {"number": line.number, "text": line.text} for line in left[i1:i2]
                ],
                "candidate_lines": [
                    {"number": line.number, "text": line.text} for line in right[j1:j2]
                ],
            }
        )
    summary["hunk_count"] = len(hunks)
    return summary, hunks
