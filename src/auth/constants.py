from enum import StrEnum

MAX_USER_NAME_LEN = 31

USER_TYPE_LEN = 10
class UserType(StrEnum):
    """
    Enum of possible user types.
    """
    USER = 'user'
    """User has permissions (type) of regular user"""
    ADMIN = 'admin'
    """User has permissions (type) of admin"""