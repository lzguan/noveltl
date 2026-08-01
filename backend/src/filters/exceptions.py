from src.exceptions import NotFoundException


class FunctionNotFoundException(NotFoundException):
    pass


class WorkflowNotFoundException(NotFoundException):
    pass


class InstanceNotFoundException(NotFoundException):
    pass


class GroupingNotFoundException(NotFoundException):
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
