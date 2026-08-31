import asyncio
import json
from decimal import Decimal
from pathlib import Path

from pydantic_ai.usage import RunUsage

from agent_evals.cli import format_run_progress
from agent_evals.corpora import CorpusImportSpec, import_flat_export
from agent_evals.execution import ReplicaResult, RunContext, run_evaluation
from agent_evals.progress import RunProgress
from agent_evals.run_configs import create_run_config
from agent_evals.schemas import RunConfig
from agent_evals.storage import EvalWorkspace, load_yaml_model


def _workspace_with_config(tmp_path: Path) -> EvalWorkspace:
    source = tmp_path / "novel.json"
    source.write_text(
        json.dumps(
            {
                "chapters": [
                    {
                        "chapterNum": number,
                        "chapterTitle": f"Chapter {number}",
                        "chapterContentText": f"Content {number}",
                    }
                    for number in range(1, 4)
                ]
            }
        ),
        encoding="utf-8",
    )
    workspace = EvalWorkspace(tmp_path / "evals")
    workspace.ensure()
    import_flat_export(
        source,
        workspace,
        CorpusImportSpec(id="test-novel", title="Test novel", language_code="zh"),
    )
    create_run_config(
        workspace,
        RunConfig.model_validate(
            {
                "id": "runner-contract",
                "change": "Exercise the runner artifact contract.",
                "objectives": ["Produce inspectable replica outcomes."],
                "degradation_guardrails": ["Do not lose completed chapter information."],
                "decision_rule": "The artifact is complete.",
                "corpus": "test-novel",
                "chapters": {"start_inclusive": 1, "end_inclusive": 3},
                "agent": {
                    "model_name": "deepseek:deepseek-v4-flash-none",
                    "toolsets": [{"name": "glossary_terms"}],
                },
                "execution": {"replicas": 3, "max_parallel": 2},
            }
        ),
    )
    return workspace


def test_runner_snapshots_config_limits_parallelism_and_records_terminal_outcomes(tmp_path: Path) -> None:
    workspace = _workspace_with_config(tmp_path)
    active = 0
    observed_parallelism = 0
    progress_events: list[RunProgress] = []

    async def execute_replica(context: RunContext, index: int, replica_dir: Path) -> ReplicaResult:
        nonlocal active, observed_parallelism
        assert [chapter.number for chapter in context.dataset.chapters] == [1, 2, 3]
        assert context.config.agent.model_name == "deepseek:deepseek-v4-flash-none"
        active += 1
        observed_parallelism = max(observed_parallelism, active)
        try:
            await asyncio.sleep(0.01)
            if index == 2:
                return ReplicaResult(
                    index=index,
                    status="failed",
                    completed_chapters=(1,),
                    usage=RunUsage(requests=1, input_tokens=10, output_tokens=2),
                    failure={"type": "SyntheticFailure", "message": "expected"},
                )
            return ReplicaResult(
                index=index,
                status="completed",
                completed_chapters=(1, 2, 3),
                usage=RunUsage(requests=3, input_tokens=30, output_tokens=6),
            )
        finally:
            active -= 1

    result = asyncio.run(
        run_evaluation(
            workspace,
            "runner-contract",
            database_url="postgresql://unused/unused",
            replica_executor=execute_replica,
            progress_reporter=progress_events.append,
        )
    )

    assert result.status == "failed"
    assert observed_parallelism == 2
    assert load_yaml_model(result.path / "config.yaml", RunConfig).id == "runner-contract"
    manifest = json.loads((result.path / "run.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["corpus"]["fingerprint"]
    assert manifest["usage"]["requests"] == 7
    assert [replica["status"] for replica in manifest["replicas"]] == ["completed", "failed", "completed"]
    assert manifest["replicas"][1]["completedChapters"] == [1]
    assert progress_events[0].kind == "run_started"
    assert progress_events[0].run_path == result.path
    assert progress_events[-1].kind == "run_finished"
    assert progress_events[-1].status == "failed"
    assert sum(event.kind == "replica_started" for event in progress_events) == 3
    assert sum(event.kind == "replica_finished" for event in progress_events) == 3


def test_cli_formats_chapter_progress_with_replica_and_run_costs(tmp_path: Path) -> None:
    progress = RunProgress(
        kind="chapter_completed",
        run_id="run-1",
        run_path=tmp_path,
        replica=2,
        chapter_num=129,
        attempt=1,
        replica_cost_usd=Decimal("0.1234567"),
        run_cost_usd=Decimal("0.2345678"),
    )

    assert format_run_progress(progress) == (
        "[replica 002] chapter 129 completed "
        "(attempt 1; replica $0.123457; run $0.234568)"
    )
