from enum import IntEnum, StrEnum

MAX_MODEL_NAME_LEN = 128
MAX_PARAMS_SIZE_BYTES = 10240
MAX_PARAMS_FIELDS = 50

class AutoLabelProgress(StrEnum):
    """
    Status for an autolabel in database. One of 'failed', 'pending', 'processing', 'done'
    """

    FAILED = 'failed'
    """Task for this autolabel failed"""
    PENDING = 'pending'
    """Task for this autolabel queueing"""
    PROCESSING = 'processing'
    """Task for this autolabel currently processing"""
    DONE = 'done'
    """Task for this autolabel succeeded"""

class SepPriority(IntEnum):
    HIGH = 1
    MED = 2
    LOW = 3
