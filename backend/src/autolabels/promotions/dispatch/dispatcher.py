import uuid
from typing import Protocol


class PromotionDispatcher(Protocol):
    async def aenqueue(self, promotion_id: uuid.UUID) -> None: ...
