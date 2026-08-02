import asyncio
import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from kombu.serialization import dumps

from src.filters.celery_app import app
from src.filters.dispatch.celery import CeleryRunnerDispatcher, run_runner_task
from src.filters.exceptions import RunnerEnqueueFailedException
from src.filters.runners.python.group_runner import PythonGroupInput


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

    @pytest.mark.asyncio
    async def test_aenqueue_offloads_enqueue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        to_thread = AsyncMock()
        monkeypatch.setattr(asyncio, "to_thread", to_thread)
        dispatcher = CeleryRunnerDispatcher()
        job_id = uuid.uuid4()
        runner_input = _group_input()

        await dispatcher.aenqueue(job_id, runner_input)

        to_thread.assert_awaited_once_with(dispatcher.enqueue, job_id, runner_input)

    def test_task_reconstructs_runner_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        run_runner = Mock()
        monkeypatch.setattr("src.filters.dispatch.celery.run_runner", run_runner)
        job_id = uuid.uuid4()
        runner_input = _group_input()
        payload = runner_input.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)

        run_runner_task(str(job_id), payload)

        run_runner.assert_called_once_with(job_id, runner_input)

    def test_task_and_worker_configuration(self) -> None:
        assert run_runner_task.soft_time_limit == 600
        assert run_runner_task.time_limit == 660
        assert app.conf.include == ["src.filters.dispatch.celery"]
        assert app.conf.worker_pool == "prefork"
        assert app.conf.worker_concurrency == 2
        assert app.conf.worker_prefetch_multiplier == 1
