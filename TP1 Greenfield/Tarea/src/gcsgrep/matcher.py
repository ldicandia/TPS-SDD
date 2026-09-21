"""Literal line matching for gcsgrep."""


def find_matches(lines, pattern: str, ignore_case: bool = False):
    """Yield ``(line_number, line)`` for every matching line."""
    needle = pattern.casefold() if ignore_case else pattern
    for number, line in enumerate(lines, start=1):
        haystack = line.casefold() if ignore_case else line
        if needle in haystack:
            yield number, line
