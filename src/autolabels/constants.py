from enum import StrEnum

MAX_MODEL_NAME_LEN = 128

class AutoLabelStatus(StrEnum):
    """
    Status for an autolabel in database. One of 'failed', 'pending', 'done'
    """

    FAILED = 'failed'
    """Task for this autolabel failed"""
    PENDING = 'pending'
    """Task for this autolabel in progress"""
    DONE = 'done'
    """Task for this autolabel succeeded"""
