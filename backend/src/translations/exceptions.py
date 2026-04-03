"""
Exceptions relating to novel translation jobs.
"""

from ..exceptions import NotFoundException


class NovelTranslationJobNotFoundException(NotFoundException):
    pass


class TranslationEnqueueFailedException(Exception):
    """
    Exception raised when enqueuing a novel translation job fails.
    """

    pass


class TranslationQueueFullException(TranslationEnqueueFailedException):
    """
    Raised when enqueue failed due to queue overflow.
    """

    pass
