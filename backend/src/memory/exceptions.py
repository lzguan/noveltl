from src.exceptions import DuplicateException, NotFoundException


class MemoryNotFoundException(NotFoundException):
    pass


class MemoryGroupNotFoundException(NotFoundException):
    pass


class MemoryWorkspaceNotFoundException(NotFoundException):
    pass


class MemoryJobClaimLostException(RuntimeError):
    pass


class MemoryJobNotFoundException(NotFoundException):
    pass


class MemoryChapterTaskNotFoundException(NotFoundException):
    pass


class MemoryJobStateException(RuntimeError):
    pass


class MemoryChapterTaskStateException(RuntimeError):
    pass


class MemoryAgentEnqueueFailedException(RuntimeError):
    pass


class GlossaryTermNotFoundException(NotFoundException):
    pass


class TermTranslationNotFoundException(NotFoundException):
    pass


class GlossaryTermAlreadyExistsException(DuplicateException):
    pass


class ConventionNotFoundException(NotFoundException):
    pass
