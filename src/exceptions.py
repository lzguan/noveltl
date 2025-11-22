"""
Global exceptions.
"""

class NotFoundException(Exception):
    """Exception for when search for object fails"""

class FieldInvalidException(Exception):
    """
    Exception for invalid database model data
    """
    pass

class DataTooLongException(FieldInvalidException):
    """
    Exception for strings that are too long
    """
    pass

class DeleteFailedException(Exception):
    """
    Exception for when deleting a resource fails
    """
    pass

class InsufficientPermissionsException(Exception):
    """
    Throw when a user has insufficient permissions to perform an operation
    """
    pass

class TooManyFoundException(Exception):
    """
    Throw when query returns more results than expected.
    """

class DuplicateException(Exception):
    """
    Throw when trying to add an object with a unique constraint into database.
    """

class UnknownError(Exception):
    """
    Exception for undetermined errors
    """
    pass