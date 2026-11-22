import uuid
from typing import Protocol


class AutoLabelDispatcher(Protocol):
    """
    Abstract class for enqueuing an autolabel request to some queue.
    """

    def enqueue(
        self,
        job_id: uuid.UUID,
        auto_label_id: uuid.UUID,
    ) -> None:
        """
        Enqueue a request.

        Args:
            job_id: String id to queue job with.
            auto_label_id: Integer identifier for the AutoLabel being operated on in db.
            params: Parameters for the NER model.

        Raises:
            QueueFullException: Queue is full.
            EnqueueFailedException: Enqueue failed for some other reason.
        """
        ...

    async def aenqueue(
        self,
        job_id: uuid.UUID,
        auto_label_id: uuid.UUID,
    ) -> None:
        """
        Enqueue a request.

        Args:
            job_id: String id to queue job with.
            auto_label_id: Integer identifier for the AutoLabel being operated on in db.
            params: Parameters for the NER model.

        Raises:
            QueueFullException: Queue is full.
            EnqueueFailedException: Enqueue failed for some other reason.
        """
        ...
