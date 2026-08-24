import asyncio
import threading
import uuid
from unittest.mock import Mock

import pytest
from kombu.serialization import dumps

from src.filters.celery_app import app
from src.filters.dispatch.celery import CeleryRunnerDispatcher, run_runner_task
from src.filters.exceptions import RunnerEnqueueFailedException
from src.filters.runners.python.annotation_runner import (
    NewStringFieldRequest,
    PythonAnnotationInput,
)
from src.filters.runners.python.group_runner import PythonGroupInput
from src.filters.worker.tasks import run_runner, runners


def _group_input() -> PythonGroupInput:
    return PythonGroupInput(
        runtime_name="python",
        runner_name="group",
        grouping_id=uuid.uuid4(),
    )


class TestCeleryRunnerDispatcher:
    def test_enqueue_publishes_json_serializable_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        apply_async = Mock()
        monkeypatch.setattr(run_runner_task, "apply_async", apply_async)
        job_id = uuid.uuid4()
        runner_input = _group_input()

        CeleryRunnerDispatcher().enqueue(job_id, runner_input)

        payload = runner_input.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)
        dumps((str(job_id), payload), serializer="json")
        apply_async.assert_called_once_with((str(job_id), payload), task_id=str(job_id))

    def test_enqueue_translates_publish_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(run_runner_task, "apply_async", Mock(side_effect=RuntimeError("broker unavailable")))

        with pytest.raises(RunnerEnqueueFailedException, match="broker unavailable"):
            CeleryRunnerDispatcher().enqueue(uuid.uuid4(), _group_input())

    def test_aenqueue_runs_enqueue_on_a_worker_thread(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dispatcher = CeleryRunnerDispatcher()
        job_id = uuid.uuid4()
        runner_input = _group_input()
        event_loop_thread = threading.get_ident()
        received: list[tuple[uuid.UUID, PythonGroupInput, int]] = []

        def recording_enqueue(received_job_id: uuid.UUID, received_input: PythonGroupInput) -> None:
            received.append((received_job_id, received_input, threading.get_ident()))

        monkeypatch.setattr(dispatcher, "enqueue", recording_enqueue)

        asyncio.run(dispatcher.aenqueue(job_id, runner_input))

        assert len(received) == 1
        assert received[0][:2] == (job_id, runner_input)
        assert received[0][2] != event_loop_thread

    def test_task_reconstructs_runner_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        run_runner = Mock()
        monkeypatch.setattr("src.filters.dispatch.celery.run_runner", run_runner)
        job_id = uuid.uuid4()
        runner_input = _group_input()
        payload = runner_input.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)

        run_runner_task(str(job_id), payload)

        run_runner.assert_called_once_with(job_id, runner_input)

    def test_task_and_worker_configuration(self) -> None:
        assert run_runner_task.soft_time_limit is not None
        assert run_runner_task.soft_time_limit > 0
        assert run_runner_task.time_limit is not None
        assert run_runner_task.time_limit > run_runner_task.soft_time_limit
        assert app.conf.include == ["src.filters.dispatch.celery"]
        assert app.conf.worker_pool == "prefork"
        assert app.conf.worker_concurrency == 2
        assert app.conf.worker_prefetch_multiplier == 1

    def test_worker_routes_annotation_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        runner = Mock()
        monkeypatch.setitem(runners["python"], "annotation", runner)
        job_id = uuid.uuid4()
        runner_input = PythonAnnotationInput(
            runtime_name="python",
            runner_name="annotation",
            workflow_id=uuid.uuid4(),
            new_fields={"note": NewStringFieldRequest(type="string")},
        )

        run_runner(job_id, runner_input)

        runner.execute.assert_called_once_with(job_id, runner_input)
