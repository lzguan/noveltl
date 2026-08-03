from src.exceptions import NotFoundException


class FunctionNotFoundException(NotFoundException):
    pass


class FunctionAlreadyExistsException(Exception):
    """Raised when a function namespace and name are already registered."""

    pass


class WorkflowNotFoundException(NotFoundException):
    pass


class InstanceNotFoundException(NotFoundException):
    pass


class GroupingNotFoundException(NotFoundException):
    pass


class GroupingAlreadyExistsException(Exception):
    """Raised when a workflow already has the requested grouping function."""

    pass


class WorkflowNotReadyException(Exception):
    pass


class GroupingNotReadyException(Exception):
    pass


class InvalidInstanceQueryException(Exception):
    pass


class GroupingValueTypeMismatchException(InvalidInstanceQueryException):
    pass


class InvalidSortKeyException(InvalidInstanceQueryException):
    pass


class UnsupportedSortTypeException(InvalidInstanceQueryException):
    pass


class InvalidRunnerRequestException(Exception):
    """Raised when a runner function is incompatible with its source."""

    pass


class RunnerEnqueueFailedException(Exception):
    """Raised when a filter runner task cannot be published."""

    pass
