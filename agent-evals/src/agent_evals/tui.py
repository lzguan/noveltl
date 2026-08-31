from collections.abc import Callable
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from agent_evals.storage import EvalWorkspace, list_files

RowsProvider = Callable[[EvalWorkspace], list[tuple[str, str]]]


class HomeScreen(Screen[None]):
    BINDINGS = [Binding("q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="home"):
            yield Static("NovelTL Agent Evaluations", id="title")
            yield Label("Choose a workflow. The first scaffold provides local discovery and validation.")
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


def _yaml_rows(directory: Path) -> list[tuple[str, str]]:
    return [(path.name, str(path)) for path in list_files(directory, {".yaml", ".yml"})]


def _corpus_rows(workspace: EvalWorkspace) -> list[tuple[str, str]]:
    return [
        (path.name, str(path))
        for path in sorted(workspace.novels.iterdir(), key=lambda item: item.name.casefold())
        if path.is_dir() and (path / "catalog.json").is_file()
    ]


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
    """

    def __init__(self, workspace: EvalWorkspace) -> None:
        super().__init__()
        self.workspace = workspace

    def on_mount(self) -> None:
        self.install_screen(ResourceScreen("Corpora", self.workspace, _corpus_rows), name="corpora")
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
