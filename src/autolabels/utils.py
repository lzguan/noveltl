from typing import Protocol, Dict
from arq import ArqRedis
from .exceptions import *
from redis.exceptions import ConnectionError, TimeoutError, ResponseError

class AutoLabelDispatcher(Protocol):
    """
    Abstract class for enqueuing an autolabel request to some queue.
    """
    async def enqueue(
        self,
        auto_label_id : int,
        text : str,
        model_name : str, 
        model_params : Dict[str, str | int | float | bool]
    ) -> None:
        """
        Enqueue a request.

        Args:
            auto_label_id: Integer identifier for the AutoLabel being operated on in db.
            text: Text of chapter.
            model_name: Name of NER model.
            model_params: Params passed into NER model.
        
        Raises:
            QueueFullException: Queue is full.
            EnqueueFailedException: Enqueue failed for some other reason.
        """
        ...

class ArqDispatcher(AutoLabelDispatcher):
    def __init__(self, redis_pool : ArqRedis) -> None:
        self.redis = redis_pool
        
    async def enqueue(
            self, job_id : str, 
            auto_label_id: int, 
            text: str, 
            model_name: str, 
            model_params: Dict[str, str | int | float | bool]
        ) -> None:
        try:
            await self.redis.enqueue_job('autolabel_infer', job_id, auto_label_id, text, model_name, model_params, _job_id=job_id)
        except (ConnectionError, TimeoutError, OSError) as e:
            raise EnqueueFailedException(f"Redis connection failed: {str(e)}") from e
        except ResponseError as e:
            if "OOM" in str(e):
                raise QueueFullException("Redis memory is full") from e
            # If it's another protocol error, treat as generic failure
            raise EnqueueFailedException(f"Redis protocol error: {str(e)}") from e
        except (TypeError, ValueError) as e:
             raise EnqueueFailedException(f"Failed to serialize job data: {str(e)}") from e