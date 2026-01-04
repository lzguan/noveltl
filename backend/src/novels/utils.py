from .models import *
from ..auth.models import *
from ..auth.exceptions import *

def check_permissions(current_user : User, **kwargs) -> None:
    """
    Placeholder for authorization. 

    Raises:
        InsufficientPermissionsException: In the case that the user does not have sufficient permissions.
    """
    return