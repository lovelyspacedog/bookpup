"""Comic archive read failures (user message + optional tool stderr)."""

from __future__ import annotations


class ComicReadError(ValueError):
    def __init__(self, message: str, *, debug_stderr: str = "") -> None:
        super().__init__(message)
        self.debug_stderr = debug_stderr