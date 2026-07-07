from __future__ import annotations

import re


_SECRET_PATTERNS = [
    re.compile(r"\b(sk-(?:proj-|admin-)?)[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\b(oai-)[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(bearer\s+)(?!sk-|oai-)([A-Za-z0-9_\-\.]{12,})"),
    re.compile(r"(?i)(token\s*=\s*)([A-Za-z0-9_\-\.]{8,})"),
    re.compile(r"(?i)(api[_-]?key\s*=\s*)([A-Za-z0-9_\-\.]{8,})"),
]


def redact_secret(value: object) -> str:
    text = "" if value is None else str(value)
    redacted = text
    for pattern in _SECRET_PATTERNS:
        def repl(match: re.Match[str]) -> str:
            prefix = match.group(1)
            return f"{prefix}...redacted"

        redacted = pattern.sub(repl, redacted)
    return redacted
