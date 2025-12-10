"""
Exceptions used in the autolabeling service
"""
from ..exceptions import *

class ChunkTooLargeException(Exception):
    """
    Exception raised when a text chunk exceeds the maximum allowed size.
    """
    pass

class TokenDoesNotExistException(Exception):
    """
    Exception raised when a token is expected but not found in text.
    """
    pass

class AutoLabelNotFoundException(NotFoundException):
    pass

class EnqueueFailedException(Exception):
    """
    Exception raised from `AutoLabelDispatcher.enqueue()`. 
    """
    pass

class QueueFullException(EnqueueFailedException):
    """
    Raise when exception occured due to queue overflow.
    """