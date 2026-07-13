from pathlib import Path


class TestDataError(Exception):
    """Base error for invalid or inconsistent test data."""


class UnsupportedDocumentError(TestDataError):
    def __init__(self, kind: object, version: object) -> None:
        super().__init__(f"Unsupported test-data document kind/version: {kind!r}/{version!r}")


class ReferenceError(TestDataError):
    def __init__(self, message: str, path: Path | None = None) -> None:
        suffix = f" ({path})" if path is not None else ""
        super().__init__(f"{message}{suffix}")


class DuplicateIdError(TestDataError):
    def __init__(self, logical_id: str) -> None:
        super().__init__(f"Duplicate logical test-data ID: {logical_id}")


class LockMismatchError(TestDataError):
    """The committed catalog lock differs from the computed lock."""
