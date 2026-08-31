import json
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError
from src.datasets.errors import TestDataError

from agent_evals.corpora import (
    CorpusImportError,
    CorpusImportSpec,
    discover_corpora,
    import_corpus,
    inspect_corpus,
    resolve_corpus,
)
from agent_evals.schemas import Checkpoint, RunConfig
from agent_evals.storage import EvalWorkspace, list_files, load_yaml_model

app = typer.Typer(name="agent-eval", no_args_is_help=True, help="Evaluate the NovelTL memory agent locally.")
corpus_app = typer.Typer(no_args_is_help=True, help="Manage private evaluation corpora.")
checkpoint_app = typer.Typer(no_args_is_help=True, help="Manage checkpoint definitions.")
config_app = typer.Typer(no_args_is_help=True, help="Manage run configurations.")
run_app = typer.Typer(no_args_is_help=True, help="Launch and inspect evaluation runs.")
review_app = typer.Typer(no_args_is_help=True, help="Review checkpoint outcomes.")
report_app = typer.Typer(no_args_is_help=True, help="Summarize and compare evaluation runs.")

app.add_typer(corpus_app, name="corpus")
app.add_typer(checkpoint_app, name="checkpoint")
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


def _validate(path: Path, model: type[Checkpoint] | type[RunConfig]) -> None:
    try:
        value = load_yaml_model(path, model)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Valid {model.__name__}: {value.id}")


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
def list_checkpoints() -> None:
    _print_paths(list_files(_workspace().checkpoints, {".yaml", ".yml"}))


@checkpoint_app.command("validate")
def validate_checkpoint(path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]) -> None:
    _validate(path, Checkpoint)


@config_app.command("list")
def list_configs() -> None:
    _print_paths(list_files(_workspace().run_configs, {".yaml", ".yml"}))


@config_app.command("validate")
def validate_config(path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]) -> None:
    _validate(path, RunConfig)


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
