"""
Exceptions for novels and chapters
"""

from ..exceptions import DeleteFailedException, FieldInvalidException, NotFoundException, TooManyFoundException


class NovelNotFoundException(NotFoundException):
    pass


class ChapterNotFoundException(NotFoundException):
    pass


class ChapterContentNotFoundException(NotFoundException):
    pass


class NovelTooManyFoundException(TooManyFoundException):
    pass


class ChapterDeleteFailedException(DeleteFailedException):
    pass


class ChapterNumDuplicateException(FieldInvalidException):
    pass


class ChapterContentOutdatedException(Exception):
    pass


class SourceWorkNotFoundException(NotFoundException):
    pass
