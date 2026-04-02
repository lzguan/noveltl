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
