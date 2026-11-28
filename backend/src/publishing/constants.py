from typing import Literal

type TargetRole = Literal["owner", "publisher"]
type PublishJobStatus = Literal["pending", "processing", "completed", "failed"]
type PublishMode = Literal["all", "outdated", "range"]

ACTIVE_PUBLISH_JOB_STATUSES: tuple[PublishJobStatus, ...] = ("pending", "processing")
READER_PROTOCOL_VERSION = 1
