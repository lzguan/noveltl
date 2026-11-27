import asyncio
import threading
import uuid
from unittest.mock import Mock

import pytest

from src.autolabels.exceptions import EnqueueFailedException
from src.autolabels.inference.celery_app import app
from src.autolabels.inference.dispatch.celery import celery_infer
from src.autolabels.inference.dispatch.celery_dispatcher import CeleryDispatcher
from src.autolabels.inference.task_names import CELERY_INFER


class TestCeleryDispatcher:
    def test_enqueue_publishes_task_with_string_job_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Published by name, so the API never imports the inference implementation.
        send_task = Mock()
        monkeypatch.setattr(app, "send_task", send_task)
        job_id = uuid.uuid4()
        auto_label_id = uuid.uuid4()

        CeleryDispatcher().enqueue(job_id, auto_label_id)

        send_task.assert_called_once_with(CELERY_INFER, args=(job_id, auto_label_id), task_id=str(job_id))
        assert celery_infer.name == CELERY_INFER

    def test_enqueue_translates_publish_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(app, "send_task", Mock(side_effect=RuntimeError("broker unavailable")))

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
