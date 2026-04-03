"""
Exceptions related to authorization
"""

from ..exceptions import DuplicateException, NotFoundException


class UserNotFoundException(NotFoundException):
    pass


class UserAuthenticationFailedException(Exception):
    pass


class UserNameDuplicateException(DuplicateException):
    pass
