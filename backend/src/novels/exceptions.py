"""
Exceptions for novels and chapters
"""

from ..exceptions import DeleteFailedException, FieldInvalidException, NotFoundException, TooManyFoundException


class NovelNotFoundException(NotFoundException):
    pass

class RawChapterNotFoundException(NotFoundException):
    pass

class RawChapterRevisionNotFoundException(NotFoundException):
    pass

class NovelTooManyFoundException(TooManyFoundException):
    pass

class ChapterNumDuplicateException(FieldInvalidException):
    pass

class RawChapterRevisionMakePrimaryFailedException(Exception):
    pass

class RawChapterRevisionNotPublicException(Exception):
    pass

class DeleteRawChapterRevisionFailedException(DeleteFailedException):
    pass

class RawChapterRevisionNotFinalException(Exception):
    pass

class NovelParentCircularReferenceException(Exception):
    pass
