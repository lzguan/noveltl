"""
Exceptions for novels and chapters
"""

from ..exceptions import DeleteFailedException, FieldInvalidException, NotFoundException, TooManyFoundException


class NovelNotFoundException(NotFoundException):
    pass

class ChapterNotFoundException(NotFoundException):
    pass

class RevisionNotFoundException(NotFoundException):
    pass

class NovelTooManyFoundException(TooManyFoundException):
    pass

class ChapterNumDuplicateException(FieldInvalidException):
    pass

class RevisionMakePrimaryFailedException(Exception):
    pass

class RevisionNotPublicException(Exception):
    pass

class DeleteRevisionFailedException(DeleteFailedException):
    pass

class RevisionNotFinalException(Exception):
    pass
