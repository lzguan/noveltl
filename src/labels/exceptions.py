"""
Exceptions relating to labels.
"""

from ..exceptions import *

class LabelGroupNotFoundException(NotFoundException):
    pass

class LabelDataNotFoundException(NotFoundException):
    pass

class LabelDataRevisionDuplicateException(DuplicateException):
    pass

class LabelInvalidOperationException(Exception):
    pass

class LabelWordMismatchInvalidOperationException(LabelInvalidOperationException):
    pass

class LabelOutOfBoundsInvalidOperationException(LabelInvalidOperationException):
    pass

class LabelNotExistsInvalidOperationException(LabelInvalidOperationException):
    pass

class LabelExclusionViolationInvalidOperationException(LabelInvalidOperationException):
    pass