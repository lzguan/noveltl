from src.exceptions import NotFoundException


class FunctionNotFoundException(NotFoundException):
    pass


class WorkflowNotFoundException(NotFoundException):
    pass


class InstanceNotFoundException(NotFoundException):
    pass
