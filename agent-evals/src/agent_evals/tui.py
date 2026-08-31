import asyncio
from collections.abc import Callable
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from agent_evals.corpora import CorpusImportSpec, CorpusSummary, discover_corpora, import_corpus, inspect_corpus
from agent_evals.storage import EvalWorkspace, list_files

RowsProvider = Callable[[EvalWorkspace], list[tuple[str, str]]]


class HomeScreen(Screen[None]):
    BINDINGS = [Binding("q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="home"):
            yield Static("NovelTL Agent Evaluations", id="title")
            yield Label("Choose a workflow for local memory-agent evaluation.")
            yield Button("Corpora", id="corpora")
            yield Button("Checkpoints", id="checkpoints")
            yield Button("Run configs", id="configs")
            yield Button("Runs", id="runs")
            yield Button("Reviews", id="reviews")
            yield Button("Reports", id="reports")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.push_screen(event.button.id or "")


class ResourceScreen(Screen[None]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, title: str, workspace: EvalWorkspace, provider: RowsProvider) -> None:
        super().__init__()
        self.resource_title = title
        self.workspace = workspace
        self.provider = provider

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="resource"):
            yield Static(self.resource_title, classes="screen-title")
            yield DataTable(id="entries")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#entries", DataTable)
        table.add_columns("Name", "Location")
        for name, location in self.provider(self.workspace):
            table.add_row(name, location)


class CorpusImportScreen(ModalScreen[CorpusSummary | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, workspace: EvalWorkspace) -> None:
        super().__init__()
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        with Container(id="import-dialog"):
            yield Static("Import corpus", classes="screen-title")
            yield Label("Source: bulk chapter upload JSON or existing catalog directory")
            yield Input(placeholder="/path/to/source", id="import-source")
            yield Input(placeholder="cn-fantasy-001", id="import-id")
            yield Input(placeholder="Novel title", id="import-title")
            yield Input(placeholder="zh", id="import-language")
            yield Label("", id="import-status")
            with Horizontal(classes="actions"):
                yield Button("Import", id="confirm-import", variant="primary")
                yield Button("Cancel", id="cancel-import")

    def action_cancel(self) -> None:
        self.dismiss(None)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-import":
            self.dismiss(None)
            return
        if event.button.id != "confirm-import":
            return

        source = Path(self.query_one("#import-source", Input).value).expanduser()
        corpus_id = self.query_one("#import-id", Input).value.strip()
        title = self.query_one("#import-title", Input).value.strip()
        language = self.query_one("#import-language", Input).value.strip()
        status = self.query_one("#import-status", Label)
        if not source.exists() or not corpus_id:
            status.update("Source must exist and corpus ID is required.")
            return
        flat_spec = None
        if source.is_file():
            if not title or not language:
                status.update("Title and language are required for upload JSON.")
                return
            try:
                flat_spec = CorpusImportSpec(id=corpus_id, title=title, language_code=language)
            except ValueError as exc:
                status.update(str(exc))
                return

        event.button.disabled = True
        status.update("Importing…")
        try:
            summary = await asyncio.to_thread(
                import_corpus,
                source,
                self.workspace,
                corpus_id=corpus_id,
                flat_spec=flat_spec,
            )
        except Exception as exc:
            event.button.disabled = False
            status.update(str(exc))
            return
        self.dismiss(summary)


class CorpusScreen(Screen[None]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, workspace: EvalWorkspace) -> None:
        super().__init__()
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="resource"):
            yield Static("Corpora", classes="screen-title")
            with Horizontal(classes="actions"):
                yield Button("Import", id="open-import", variant="primary")
                yield Button("Validate selected", id="validate-corpus")
                yield Button("Refresh", id="refresh-corpora")
            yield Label("", id="corpus-status")
            yield DataTable(id="corpus-entries")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#corpus-entries", DataTable)
        table.add_columns("ID", "Language", "Chapters", "Title", "Fingerprint")
        self.refresh_corpora()

    def refresh_corpora(self) -> None:
        table = self.query_one("#corpus-entries", DataTable)
        status = self.query_one("#corpus-status", Label)
        table.clear()
        try:
            summaries = discover_corpora(self.workspace)
        except Exception as exc:
            status.update(str(exc))
            return
        for summary in summaries:
            table.add_row(
                summary.id,
                summary.language_code,
                str(summary.chapter_count),
                summary.title,
                summary.fingerprint[:12],
            )
        status.update(f"{len(summaries)} corpus item(s)")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-corpora":
            self.refresh_corpora()
        elif event.button.id == "open-import":
            self.app.push_screen(CorpusImportScreen(self.workspace), self._import_finished)
        elif event.button.id == "validate-corpus":
            table = self.query_one("#corpus-entries", DataTable)
            status = self.query_one("#corpus-status", Label)
            if table.row_count == 0:
                status.update("No corpus selected.")
                return
            corpus_id = str(table.get_row_at(table.cursor_row)[0])
            event.button.disabled = True
            status.update(f"Validating {corpus_id}…")
            try:
                summary = await asyncio.to_thread(
                    inspect_corpus,
                    self.workspace.novels / corpus_id,
                    corpus_id=corpus_id,
                    verify_lock=True,
                )
            except Exception as exc:
                status.update(str(exc))
            else:
                status.update(f"Valid {summary.id}: {summary.fingerprint}")
            finally:
                event.button.disabled = False

    def _import_finished(self, summary: CorpusSummary | None) -> None:
        if summary is not None:
            self.refresh_corpora()
            self.query_one("#corpus-status", Label).update(f"Imported {summary.id}")


def _yaml_rows(directory: Path) -> list[tuple[str, str]]:
    return [(path.name, str(path)) for path in list_files(directory, {".yaml", ".yml"})]


def _run_rows(workspace: EvalWorkspace) -> list[tuple[str, str]]:
    return [(path.name, str(path)) for path in sorted(workspace.runs.glob("*/*")) if path.is_dir()]


def _artifact_rows(workspace: EvalWorkspace, filename: str) -> list[tuple[str, str]]:
    return [(path.parent.name, str(path)) for path in sorted(workspace.runs.glob(f"*/*/{filename}"))]


class AgentEvalApp(App[None]):
    CSS = """
    HomeScreen {
        align-horizontal: center;
    }
    #home {
        width: 72;
        height: auto;
        margin-top: 2;
        padding: 1 2;
        border: round $accent;
    }
    #home Button {
        width: 100%;
        margin-top: 1;
    }
    #title, .screen-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #resource {
        padding: 1 2;
    }
    #entries {
        height: 1fr;
    }
    #corpus-entries {
        height: 1fr;
    }
    .actions {
        height: auto;
        margin-bottom: 1;
    }
    .actions Button {
        margin-right: 1;
    }
    CorpusImportScreen {
        align: center middle;
    }
    #import-dialog {
        width: 72;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    #import-dialog Input {
        margin-bottom: 0;
    }
    """

    def __init__(self, workspace: EvalWorkspace) -> None:
        super().__init__()
        self.workspace = workspace

    def on_mount(self) -> None:
        self.install_screen(CorpusScreen(self.workspace), name="corpora")
        self.install_screen(
            ResourceScreen("Checkpoints", self.workspace, lambda workspace: _yaml_rows(workspace.checkpoints)),
            name="checkpoints",
        )
        self.install_screen(
            ResourceScreen("Run configs", self.workspace, lambda workspace: _yaml_rows(workspace.run_configs)),
            name="configs",
        )
        self.install_screen(ResourceScreen("Runs", self.workspace, _run_rows), name="runs")
        self.install_screen(
            ResourceScreen(
                "Reviews",
                self.workspace,
                lambda workspace: _artifact_rows(workspace, "review.json"),
            ),
            name="reviews",
        )
        self.install_screen(
            ResourceScreen(
                "Reports",
                self.workspace,
                lambda workspace: _artifact_rows(workspace, "report.json"),
            ),
            name="reports",
        )
        self.push_screen(HomeScreen())
