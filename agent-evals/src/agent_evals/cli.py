import json
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError
from src.datasets.errors import TestDataError

from agent_evals.checkpoints import (
    CheckpointError,
    create_checkpoint,
    delete_checkpoint,
    discover_checkpoints,
    load_checkpoint,
    remove_expected_memory,
    render_checkpoint,
    resolve_checkpoint,
    set_expected_memory,
    update_checkpoint,
    validate_checkpoint_context,
)
from agent_evals.corpora import (
    CorpusImportError,
    CorpusImportSpec,
    discover_corpora,
    import_corpus,
    inspect_corpus,
    resolve_corpus,
)
from agent_evals.run_configs import (
    RunConfigError,
    create_run_config,
    delete_run_config,
    discover_run_configs,
    discover_toolset_names,
    load_run_config,
    render_run_config,
    resolve_run_config,
    update_run_config,
    validate_run_config_context,
)
from agent_evals.schemas import Checkpoint, ExpectedMemory, InclusiveChapterRange, RunConfig
from agent_evals.storage import EvalWorkspace, load_yaml_model

app = typer.Typer(name="agent-eval", no_args_is_help=True, help="Evaluate the NovelTL memory agent locally.")
corpus_app = typer.Typer(no_args_is_help=True, help="Manage private evaluation corpora.")
checkpoint_app = typer.Typer(no_args_is_help=True, help="Manage checkpoint definitions.")
checkpoint_metric_app = typer.Typer(no_args_is_help=True, help="Manage expected memories for a checkpoint.")
config_app = typer.Typer(no_args_is_help=True, help="Manage run configurations.")
run_app = typer.Typer(no_args_is_help=True, help="Launch and inspect evaluation runs.")
review_app = typer.Typer(no_args_is_help=True, help="Review checkpoint outcomes.")
report_app = typer.Typer(no_args_is_help=True, help="Summarize and compare evaluation runs.")

app.add_typer(corpus_app, name="corpus")
app.add_typer(checkpoint_app, name="checkpoint")
checkpoint_app.add_typer(checkpoint_metric_app, name="metric")
app.add_typer(config_app, name="config")
app.add_typer(run_app, name="run")
app.add_typer(review_app, name="review")
app.add_typer(report_app, name="report")


def _workspace() -> EvalWorkspace:
    workspace = EvalWorkspace()
    workspace.ensure()
    return workspace


def _print_paths(paths: list[Path], *, relative_to: Path | None = None) -> None:
    if not paths:
        typer.echo("No entries found.")
        return
    for path in paths:
        typer.echo(path.relative_to(relative_to) if relative_to is not None else path.name)


@app.command()
def paths() -> None:
    """Print the local evaluation data directories."""
    workspace = _workspace()
    for directory in workspace.local_directories():
        typer.echo(f"{directory.name}: {directory}")


@app.command()
def ui() -> None:
    """Open the interactive terminal interface."""
    from agent_evals.tui import AgentEvalApp

    AgentEvalApp(_workspace()).run()


@corpus_app.command("list")
def list_corpora() -> None:
    workspace = _workspace()
    try:
        summaries = discover_corpora(workspace)
    except (OSError, ValueError, TestDataError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if not summaries:
        typer.echo("No entries found.")
        return
    for summary in summaries:
        typer.echo(
            f"{summary.id}\t{summary.language_code}\t{summary.chapter_count} chapters\t{summary.title}"
        )


@corpus_app.command("validate")
def validate_corpus(corpus: Annotated[str, typer.Argument(help="Corpus ID or catalog directory")]) -> None:
    workspace = _workspace()
    path = resolve_corpus(workspace, corpus)
    try:
        summary = inspect_corpus(path, corpus_id=path.name, verify_lock=True)
    except (OSError, ValueError, TestDataError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Valid corpus: {summary.id} ({summary.chapter_count} chapters, {summary.fingerprint})")


@corpus_app.command("show")
def show_corpus(corpus: Annotated[str, typer.Argument(help="Corpus ID or catalog directory")]) -> None:
    workspace = _workspace()
    path = resolve_corpus(workspace, corpus)
    try:
        summary = inspect_corpus(path, corpus_id=path.name)
    except (OSError, ValueError, TestDataError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))


@corpus_app.command("import")
def import_corpus_command(
    source: Annotated[
        Path,
        typer.Argument(exists=True, readable=True, help="Bulk chapter upload JSON or catalog directory"),
    ],
    corpus_id: Annotated[str, typer.Option("--id", help="Stable private corpus ID")],
    title: Annotated[str | None, typer.Option(help="Novel title; required for upload JSON")] = None,
    language_code: Annotated[str | None, typer.Option("--language", help="Language code; required for upload JSON")] = None,
    description: Annotated[str | None, typer.Option()] = None,
    author: Annotated[str | None, typer.Option()] = None,
    novel_type: Annotated[
        Literal["original", "translation", "other"],
        typer.Option(help="Novel type"),
    ] = "original",
) -> None:
    workspace = _workspace()
    try:
        flat_spec = None
        if source.is_file():
            if title is None or language_code is None:
                raise CorpusImportError("--title and --language are required for bulk chapter upload JSON")
            flat_spec = CorpusImportSpec(
                id=corpus_id,
                title=title,
                language_code=language_code,
                description=description,
                author=author,
                novel_type=novel_type,
            )
        summary = import_corpus(source, workspace, corpus_id=corpus_id, flat_spec=flat_spec)
    except (OSError, ValueError, ValidationError, TestDataError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Imported corpus: {summary.id} ({summary.chapter_count} chapters, {summary.fingerprint})")


@checkpoint_app.command("list")
def list_checkpoints(as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False) -> None:
    try:
        summaries = discover_checkpoints(_workspace())
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if as_json:
        typer.echo(json.dumps([summary.to_dict() for summary in summaries], ensure_ascii=False, indent=2))
    elif not summaries:
        typer.echo("No entries found.")
    else:
        for summary in summaries:
            typer.echo(
                f"{summary.id}\t{summary.corpus}\t{summary.start_chapter}-{summary.end_chapter}"
                f"\t{summary.activity}\t{summary.memory_count} memories"
            )


@checkpoint_app.command("create")
def create_checkpoint_command(
    checkpoint_id: Annotated[str, typer.Argument(help="Stable checkpoint ID")],
    corpus: Annotated[str, typer.Option(help="Imported corpus ID")],
    start: Annotated[int, typer.Option(min=1, help="First chapter, inclusive")],
    end: Annotated[int, typer.Option(min=1, help="Last chapter, inclusive")],
    activity: Annotated[Literal["normal", "busy", "quiet"], typer.Option()] = "normal",
    notes: Annotated[str | None, typer.Option()] = None,
) -> None:
    workspace = _workspace()
    try:
        checkpoint = Checkpoint(
            id=checkpoint_id,
            corpus=corpus,
            chapters=InclusiveChapterRange(start_inclusive=start, end_inclusive=end),
            activity=activity,
            notes=notes,
        )
        path = create_checkpoint(workspace, checkpoint)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Created checkpoint: {checkpoint.id} ({path})")


@checkpoint_app.command("show")
def show_checkpoint(
    checkpoint: Annotated[str, typer.Argument(help="Checkpoint ID or YAML path")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False,
) -> None:
    workspace = _workspace()
    try:
        value = load_checkpoint(workspace, checkpoint)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(render_checkpoint(value, as_json=as_json))


@checkpoint_app.command("update")
def update_checkpoint_command(
    checkpoint_id: Annotated[str, typer.Argument(help="Checkpoint ID")],
    start: Annotated[int | None, typer.Option(min=1, help="Replace first chapter")] = None,
    end: Annotated[int | None, typer.Option(min=1, help="Replace last chapter")] = None,
    activity: Annotated[Literal["normal", "busy", "quiet"] | None, typer.Option()] = None,
    notes: Annotated[str | None, typer.Option(help="Replace notes")] = None,
    clear_notes: Annotated[bool, typer.Option("--clear-notes", help="Remove existing notes")] = False,
) -> None:
    workspace = _workspace()
    try:
        checkpoint = load_checkpoint(workspace, checkpoint_id)
        changes: dict[str, object] = {}
        if start is not None or end is not None:
            changes["chapters"] = InclusiveChapterRange(
                start_inclusive=start if start is not None else checkpoint.chapters.start_inclusive,
                end_inclusive=end if end is not None else checkpoint.chapters.end_inclusive,
            )
        if activity is not None:
            changes["activity"] = activity
        if notes is not None and clear_notes:
            raise CheckpointError("--notes and --clear-notes cannot be used together")
        if notes is not None or clear_notes:
            changes["notes"] = notes
        updated = update_checkpoint(workspace, checkpoint_id, **changes)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Updated checkpoint: {updated.id}")


@checkpoint_app.command("delete")
def delete_checkpoint_command(
    checkpoint_id: Annotated[str, typer.Argument(help="Checkpoint ID")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Delete without prompting")] = False,
) -> None:
    workspace = _workspace()
    try:
        resolve_checkpoint(workspace, checkpoint_id)
        if not yes and not typer.confirm(f"Delete checkpoint {checkpoint_id}?"):
            raise typer.Abort()
        delete_checkpoint(workspace, checkpoint_id)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Deleted checkpoint: {checkpoint_id}")


@checkpoint_app.command("validate")
def validate_checkpoint(checkpoint: Annotated[str, typer.Argument(help="Checkpoint ID or YAML path")]) -> None:
    workspace = _workspace()
    try:
        path = resolve_checkpoint(workspace, checkpoint)
        value = load_yaml_model(path, Checkpoint)
        validate_checkpoint_context(workspace, value)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Valid Checkpoint: {value.id}")


@checkpoint_metric_app.command("list")
def list_checkpoint_metrics(
    checkpoint_id: Annotated[str, typer.Argument(help="Checkpoint ID")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False,
) -> None:
    try:
        checkpoint = load_checkpoint(_workspace(), checkpoint_id)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if as_json:
        payload = [memory.model_dump(mode="json", exclude_none=True) for memory in checkpoint.expected_memories]
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    elif not checkpoint.expected_memories:
        typer.echo("No entries found.")
    else:
        for memory in checkpoint.expected_memories:
            typer.echo(f"{memory.id}\t{memory.memory_type}\t{memory.lifecycle}\t{memory.content}")


@checkpoint_metric_app.command("set")
def set_checkpoint_metric(
    checkpoint_id: Annotated[str, typer.Argument(help="Checkpoint ID")],
    metric_id: Annotated[str, typer.Option("--id", help="Expected-memory ID")],
    memory_type: Annotated[str, typer.Option(help="Memory type, such as fact, rel, or def")],
    content: Annotated[str, typer.Option(help="Expected memory content")],
    category: Annotated[str | None, typer.Option()] = None,
    terms: Annotated[list[str] | None, typer.Option("--term", help="Related original-language term; repeatable")] = None,
    expected_state: Annotated[Literal["active", "ended"], typer.Option()] = "active",
    lifecycle: Annotated[Literal["any", "create", "supersede", "expire"], typer.Option()] = "any",
) -> None:
    workspace = _workspace()
    try:
        memory = ExpectedMemory(
            id=metric_id,
            memory_type=memory_type,
            category=category,
            terms=terms or [],
            content=content,
            expected_state=expected_state,
            lifecycle=lifecycle,
        )
        checkpoint = set_expected_memory(workspace, checkpoint_id, memory)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Set metric: {checkpoint.id}/{memory.id}")


@checkpoint_metric_app.command("remove")
def remove_checkpoint_metric(
    checkpoint_id: Annotated[str, typer.Argument(help="Checkpoint ID")],
    metric_id: Annotated[str, typer.Argument(help="Expected-memory ID")],
) -> None:
    try:
        checkpoint = remove_expected_memory(_workspace(), checkpoint_id, metric_id)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Removed metric: {checkpoint.id}/{metric_id}")


@config_app.command("list")
def list_configs(as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False) -> None:
    try:
        summaries = discover_run_configs(_workspace())
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if as_json:
        typer.echo(json.dumps([summary.to_dict() for summary in summaries], ensure_ascii=False, indent=2))
    elif not summaries:
        typer.echo("No entries found.")
    else:
        for summary in summaries:
            typer.echo(
                f"{summary.id}\t{summary.corpus}\t{summary.start_chapter}-{summary.end_chapter}"
                f"\t{summary.profile}\t{','.join(summary.toolsets)}\t{summary.replicas} replica(s)"
            )


@config_app.command("toolsets")
def list_config_toolsets() -> None:
    """List toolsets from backend-owned memory-agent metadata."""

    for name in discover_toolset_names():
        typer.echo(name)


@config_app.command("show")
def show_config(
    config: Annotated[str, typer.Argument(help="Run config ID or YAML path")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False,
) -> None:
    try:
        value = load_run_config(_workspace(), config)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(render_run_config(value, as_json=as_json))


@config_app.command("create")
def create_config_command(
    config_id: Annotated[str, typer.Argument(help="Stable run-config ID")],
    change: Annotated[str, typer.Option(help="Experimental change under evaluation")],
    objectives: Annotated[list[str] | None, typer.Option("--objective", help="Desired improvement; repeatable")] = None,
    expected_side_effects: Annotated[
        list[str] | None,
        typer.Option("--expected-side-effect", help="Expected side effect; repeatable"),
    ] = None,
    degradation_guardrails: Annotated[
        list[str] | None,
        typer.Option("--guardrail", help="Output-quality guardrail; repeatable"),
    ] = None,
    decision_rule: Annotated[str, typer.Option(help="Rule for accepting or rejecting the change")] = "",
    corpus: Annotated[str, typer.Option(help="Imported corpus ID")] = "",
    start: Annotated[int, typer.Option(min=1, help="First chapter, inclusive")] = 1,
    end: Annotated[int, typer.Option(min=1, help="Last chapter, inclusive")] = 1,
    checkpoints: Annotated[
        list[str] | None,
        typer.Option("--checkpoint", help="Checkpoint ID; repeatable"),
    ] = None,
    profile: Annotated[str, typer.Option(help="Agent profile or model preset")] = "",
    toolsets: Annotated[
        list[str] | None,
        typer.Option("--toolset", help="Backend-registered toolset; repeatable"),
    ] = None,
    replicas: Annotated[int, typer.Option(min=1)] = 1,
    max_parallel: Annotated[int, typer.Option(min=1)] = 1,
    retries_per_chapter: Annotated[int, typer.Option(min=0)] = 0,
    max_cost_usd: Annotated[float | None, typer.Option(min=0)] = None,
    max_wall_seconds: Annotated[int | None, typer.Option(min=1)] = None,
) -> None:
    workspace = _workspace()
    try:
        config = RunConfig.model_validate(
            {
                "id": config_id,
                "change": change,
                "objectives": objectives or [],
                "expected_side_effects": expected_side_effects or [],
                "degradation_guardrails": degradation_guardrails or [],
                "decision_rule": decision_rule,
                "corpus": corpus,
                "chapters": {"start_inclusive": start, "end_inclusive": end},
                "checkpoints": checkpoints or [],
                "agent": {
                    "profile": profile,
                    "toolsets": [{"name": name, "settings": {}} for name in toolsets or []],
                },
                "execution": {
                    "replicas": replicas,
                    "max_parallel": max_parallel,
                    "retries_per_chapter": retries_per_chapter,
                },
                "budget": {
                    "max_cost_usd": max_cost_usd,
                    "max_wall_seconds": max_wall_seconds,
                },
            }
        )
        path = create_run_config(workspace, config)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Created run config: {config.id} ({path})")


@config_app.command("update")
def update_config_command(
    config_id: Annotated[str, typer.Argument(help="Run-config ID")],
    change: Annotated[str | None, typer.Option(help="Replace experimental change")] = None,
    objectives: Annotated[list[str] | None, typer.Option("--objective", help="Replace objectives; repeatable")] = None,
    expected_side_effects: Annotated[
        list[str] | None,
        typer.Option("--expected-side-effect", help="Replace expected side effects; repeatable"),
    ] = None,
    clear_expected_side_effects: Annotated[bool, typer.Option("--clear-expected-side-effects")] = False,
    degradation_guardrails: Annotated[
        list[str] | None,
        typer.Option("--guardrail", help="Replace guardrails; repeatable"),
    ] = None,
    decision_rule: Annotated[str | None, typer.Option(help="Replace decision rule")] = None,
    corpus: Annotated[str | None, typer.Option(help="Replace corpus ID")] = None,
    start: Annotated[int | None, typer.Option(min=1, help="Replace first chapter")] = None,
    end: Annotated[int | None, typer.Option(min=1, help="Replace last chapter")] = None,
    checkpoints: Annotated[
        list[str] | None,
        typer.Option("--checkpoint", help="Replace checkpoints; repeatable"),
    ] = None,
    clear_checkpoints: Annotated[bool, typer.Option("--clear-checkpoints")] = False,
    profile: Annotated[str | None, typer.Option(help="Replace agent profile")] = None,
    toolsets: Annotated[
        list[str] | None,
        typer.Option("--toolset", help="Replace toolsets; repeatable"),
    ] = None,
    replicas: Annotated[int | None, typer.Option(min=1)] = None,
    max_parallel: Annotated[int | None, typer.Option(min=1)] = None,
    retries_per_chapter: Annotated[int | None, typer.Option(min=0)] = None,
    max_cost_usd: Annotated[float | None, typer.Option(min=0)] = None,
    max_wall_seconds: Annotated[int | None, typer.Option(min=1)] = None,
    clear_budget: Annotated[bool, typer.Option("--clear-budget")] = False,
) -> None:
    workspace = _workspace()
    try:
        existing = load_run_config(workspace, config_id)
        changes: dict[str, object] = {}
        for key, value in (
            ("change", change),
            ("objectives", objectives),
            ("degradation_guardrails", degradation_guardrails),
            ("decision_rule", decision_rule),
            ("corpus", corpus),
        ):
            if value is not None:
                changes[key] = value
        if expected_side_effects is not None and clear_expected_side_effects:
            raise RunConfigError("--expected-side-effect and --clear-expected-side-effects cannot be used together")
        if expected_side_effects is not None or clear_expected_side_effects:
            changes["expected_side_effects"] = expected_side_effects or []
        if checkpoints is not None and clear_checkpoints:
            raise RunConfigError("--checkpoint and --clear-checkpoints cannot be used together")
        if checkpoints is not None or clear_checkpoints:
            changes["checkpoints"] = checkpoints or []
        if start is not None or end is not None:
            changes["chapters"] = InclusiveChapterRange(
                start_inclusive=start if start is not None else existing.chapters.start_inclusive,
                end_inclusive=end if end is not None else existing.chapters.end_inclusive,
            )
        if profile is not None or toolsets is not None:
            changes["agent"] = {
                "profile": profile if profile is not None else existing.agent.profile,
                "toolsets": (
                    [{"name": name, "settings": {}} for name in toolsets]
                    if toolsets is not None
                    else existing.agent.toolsets
                ),
            }
        if replicas is not None or max_parallel is not None or retries_per_chapter is not None:
            changes["execution"] = {
                "replicas": replicas if replicas is not None else existing.execution.replicas,
                "max_parallel": max_parallel if max_parallel is not None else existing.execution.max_parallel,
                "retries_per_chapter": (
                    retries_per_chapter
                    if retries_per_chapter is not None
                    else existing.execution.retries_per_chapter
                ),
            }
        if clear_budget and (max_cost_usd is not None or max_wall_seconds is not None):
            raise RunConfigError("Budget values and --clear-budget cannot be used together")
        if clear_budget:
            changes["budget"] = {}
        elif max_cost_usd is not None or max_wall_seconds is not None:
            changes["budget"] = {
                "max_cost_usd": max_cost_usd if max_cost_usd is not None else existing.budget.max_cost_usd,
                "max_wall_seconds": (
                    max_wall_seconds if max_wall_seconds is not None else existing.budget.max_wall_seconds
                ),
            }
        updated = update_run_config(workspace, config_id, **changes)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Updated run config: {updated.id}")


@config_app.command("delete")
def delete_config_command(
    config_id: Annotated[str, typer.Argument(help="Run-config ID")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Delete without prompting")] = False,
) -> None:
    workspace = _workspace()
    try:
        resolve_run_config(workspace, config_id)
        if not yes and not typer.confirm(f"Delete run config {config_id}?"):
            raise typer.Abort()
        delete_run_config(workspace, config_id)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Deleted run config: {config_id}")


@config_app.command("validate")
def validate_config(config: Annotated[str, typer.Argument(help="Run config ID or YAML path")]) -> None:
    workspace = _workspace()
    try:
        path = resolve_run_config(workspace, config)
        value = load_yaml_model(path, RunConfig)
        validate_run_config_context(workspace, value)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Valid RunConfig: {value.id}")


@run_app.command("list")
def list_runs() -> None:
    workspace = _workspace()
    paths = sorted(
        (path for path in workspace.runs.glob("*/*") if path.is_dir()),
        key=lambda path: path.as_posix().casefold(),
    )
    _print_paths(paths, relative_to=workspace.runs)


@review_app.command("list")
def list_reviews() -> None:
    workspace = _workspace()
    _print_paths(sorted(workspace.runs.glob("*/*/review.json")), relative_to=workspace.runs)


@report_app.command("list")
def list_reports() -> None:
    workspace = _workspace()
    _print_paths(sorted(workspace.runs.glob("*/*/report.json")), relative_to=workspace.runs)
