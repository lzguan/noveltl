import asyncio
import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from src.autolabels.dispatch.celery import CeleryDispatcher, celery_infer
from src.autolabels.exceptions import EnqueueFailedException
from src.celery_app import app


class TestCeleryDispatcher:
    def test_enqueue_publishes_task_with_string_job_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        apply_async = Mock()
        monkeypatch.setattr(celery_infer, "apply_async", apply_async)
        job_id = uuid.uuid4()
        auto_label_id = uuid.uuid4()

        CeleryDispatcher().enqueue(job_id, auto_label_id)

        apply_async.assert_called_once_with((job_id, auto_label_id), task_id=str(job_id))

    def test_enqueue_translates_publish_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(celery_infer, "apply_async", Mock(side_effect=RuntimeError("broker unavailable")))

        with pytest.raises(EnqueueFailedException, match="broker unavailable"):
            CeleryDispatcher().enqueue(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_aenqueue_offloads_enqueue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        to_thread = AsyncMock()
        monkeypatch.setattr(asyncio, "to_thread", to_thread)
        dispatcher = CeleryDispatcher()
        job_id = uuid.uuid4()
        auto_label_id = uuid.uuid4()

        await dispatcher.aenqueue(job_id, auto_label_id)

        to_thread.assert_awaited_once_with(dispatcher.enqueue, job_id, auto_label_id)

    def test_inference_task_time_limits(self) -> None:
        assert celery_infer.soft_time_limit == 600
        assert celery_infer.time_limit == 660

    def test_worker_configuration(self) -> None:
        assert app.conf.worker_pool == "prefork"
        assert app.conf.worker_concurrency == 2
        assert app.conf.worker_prefetch_multiplier == 1
