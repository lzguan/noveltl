import asyncio
import threading
import uuid
from unittest.mock import Mock

import pytest

from src.autolabels.celery_app import app
from src.autolabels.dispatch.celery import CeleryDispatcher, celery_infer
from src.autolabels.exceptions import EnqueueFailedException


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

    def test_aenqueue_runs_enqueue_on_a_worker_thread(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dispatcher = CeleryDispatcher()
        job_id = uuid.uuid4()
        auto_label_id = uuid.uuid4()
        event_loop_thread = threading.get_ident()
        received: list[tuple[uuid.UUID, uuid.UUID, int]] = []

        def recording_enqueue(received_job_id: uuid.UUID, received_auto_label_id: uuid.UUID) -> None:
            received.append((received_job_id, received_auto_label_id, threading.get_ident()))

        monkeypatch.setattr(dispatcher, "enqueue", recording_enqueue)

        asyncio.run(dispatcher.aenqueue(job_id, auto_label_id))

        assert len(received) == 1
        assert received[0][:2] == (job_id, auto_label_id)
        assert received[0][2] != event_loop_thread

    def test_inference_task_has_graceful_time_limits(self) -> None:
        assert celery_infer.soft_time_limit is not None
        assert celery_infer.soft_time_limit > 0
        assert celery_infer.time_limit is not None
        assert celery_infer.time_limit > celery_infer.soft_time_limit

    def test_worker_configuration(self) -> None:
        assert app.conf.worker_pool == "prefork"
        assert app.conf.worker_concurrency == 2
        assert app.conf.worker_prefetch_multiplier == 1
