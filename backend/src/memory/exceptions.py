from src.exceptions import DuplicateException, NotFoundException


class MemoryNotFoundException(NotFoundException):
    pass


class MemoryGroupNotFoundException(NotFoundException):
    pass


class GlossaryTermNotFoundException(NotFoundException):
    pass


class GlossaryTermAlreadyExistsException(DuplicateException):
    pass
