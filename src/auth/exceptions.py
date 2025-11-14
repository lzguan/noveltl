"""
Exceptions related to authorization
"""

from ..exceptions import *

class UserNotFoundException(NotFoundException):
    pass

class UserTooManyFoundException(TooManyFoundException):
    pass

class UserAuthenticationFailedException(Exception):
    pass

class UserNameDuplicateException(FieldInvalidException):
    pass
