"""
Exceptions relating to glossaries.
"""

from ..exceptions import DuplicateException, NotFoundException


class GlossaryNotFoundException(NotFoundException):
    pass


class GlossaryEntryNotFoundException(NotFoundException):
    pass


class GlossaryContributorNotFoundException(NotFoundException):
    pass


class DuplicateGlossaryEntryException(DuplicateException):
    pass


class DuplicateGlossaryContributorException(DuplicateException):
    pass


class InvalidSearchModeException(Exception):
    pass


class GlossaryTranslationJobNotFoundException(NotFoundException):
    pass


class EnqueueFailedException(Exception):
    """
    Exception raised when enqueuing a translation job fails.
    """

    pass


class QueueFullException(EnqueueFailedException):
    """
    Raised when enqueue failed due to queue overflow.
    """

    pass
