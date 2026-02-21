class FilterNotFoundException(Exception):
    """Raised when a filter is not found in the registry."""
    pass

class OptionsValidationException(Exception):
    """Raised when the options provided for a filter are invalid."""
    pass

class InstanceValidationException(Exception):
    """Raised when the instances provided for a filter are invalid."""
    pass

class InstanceContextValidationException(Exception):
    """Raised when the instances or contexts provided for a filter are invalid."""
    pass
