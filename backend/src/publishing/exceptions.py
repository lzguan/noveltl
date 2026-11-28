class InvalidTargetUrlException(Exception):
    pass


class PublishingNotConfiguredException(Exception):
    pass


class KeyDecryptionException(Exception):
    pass


class TargetConnectionException(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TargetNotFoundException(Exception):
    pass


class TargetPermissionException(Exception):
    pass


class LastTargetOwnerException(Exception):
    pass


class TargetMemberNotFoundException(Exception):
    pass


class PublishJobNotFoundException(Exception):
    pass


class PublishJobAlreadyActiveException(Exception):
    pass


class PublishEnqueueFailedException(Exception):
    pass
