import asyncio
from collections.abc import Callable
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Label, Static, TextArea

from agent_evals.checkpoints import (
    CheckpointSummary,
    create_checkpoint,
    delete_checkpoint,
    discover_checkpoints,
    load_checkpoint,
    save_checkpoint,
)
from agent_evals.corpora import CorpusImportSpec, CorpusSummary, discover_corpora, import_corpus, inspect_corpus
from agent_evals.run_configs import (
    RunConfigSummary,
    create_run_config,
    delete_run_config,
    discover_run_configs,
    discover_toolset_names,
    load_run_config,
    save_run_config,
)
from agent_evals.schemas import Checkpoint, ExpectedMemory, RunConfig
from agent_evals.storage import EvalWorkspace

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


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Container(classes="dialog", id="confirm-dialog"):
            yield Label(self.message)
            with Horizontal(classes="actions"):
                yield Button("Delete", id="confirm-delete", variant="error")
                yield Button("Cancel", id="cancel-delete")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-delete")


class MetricEditScreen(ModalScreen[ExpectedMemory | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, memory: ExpectedMemory | None = None) -> None:
        super().__init__()
        self.memory = memory

    def compose(self) -> ComposeResult:
        memory = self.memory
        with VerticalScroll(classes="dialog", id="metric-dialog"):
            yield Static("Expected memory", classes="screen-title")
            yield Input(value=memory.id if memory else "", placeholder="Metric ID", id="metric-id")
            yield Input(value=memory.memory_type if memory else "", placeholder="Memory type: fact, rel, def…", id="metric-type")
            yield Input(value=memory.category or "" if memory else "", placeholder="Category (optional)", id="metric-category")
            yield Input(value=", ".join(memory.terms) if memory else "", placeholder="Original-language terms, comma-separated", id="metric-terms")
            yield Input(value=memory.content if memory else "", placeholder="Expected memory content", id="metric-content")
            yield Input(value=memory.expected_state if memory else "active", placeholder="active or ended", id="metric-state")
            yield Input(value=memory.lifecycle if memory else "any", placeholder="any, create, supersede, or expire", id="metric-lifecycle")
            yield Label("", id="metric-status")
            with Horizontal(classes="actions"):
                yield Button("Apply", id="apply-metric", variant="primary")
                yield Button("Cancel", id="cancel-metric")

    def on_mount(self) -> None:
        if self.memory is not None:
            self.query_one("#metric-id", Input).disabled = True

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-metric":
            self.dismiss(None)
            return
        if event.button.id != "apply-metric":
            return
        terms = [term.strip() for term in self.query_one("#metric-terms", Input).value.split(",") if term.strip()]
        category = self.query_one("#metric-category", Input).value.strip() or None
        try:
            memory = ExpectedMemory.model_validate(
                {
                    "id": self.query_one("#metric-id", Input).value.strip(),
                    "memory_type": self.query_one("#metric-type", Input).value.strip(),
                    "category": category,
                    "terms": terms,
                    "content": self.query_one("#metric-content", Input).value.strip(),
                    "expected_state": self.query_one("#metric-state", Input).value.strip(),
                    "lifecycle": self.query_one("#metric-lifecycle", Input).value.strip(),
                }
            )
        except ValueError as exc:
            self.query_one("#metric-status", Label).update(str(exc))
            return
        self.dismiss(memory)


class CheckpointEditScreen(ModalScreen[Checkpoint | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, workspace: EvalWorkspace, checkpoint: Checkpoint | None = None) -> None:
        super().__init__()
        self.workspace = workspace
        self.checkpoint = checkpoint
        self.memories = list(checkpoint.expected_memories) if checkpoint else []

    def compose(self) -> ComposeResult:
        checkpoint = self.checkpoint
        with VerticalScroll(classes="dialog", id="checkpoint-dialog"):
            yield Static("Edit checkpoint" if checkpoint else "Create checkpoint", classes="screen-title")
            yield Input(value=checkpoint.id if checkpoint else "", placeholder="Checkpoint ID", id="checkpoint-id")
            yield Input(value=checkpoint.corpus if checkpoint else "", placeholder="Corpus ID", id="checkpoint-corpus")
            yield Input(
                value=str(checkpoint.chapters.start_inclusive) if checkpoint else "",
                placeholder="First chapter (inclusive)",
                id="checkpoint-start",
                type="integer",
            )
            yield Input(
                value=str(checkpoint.chapters.end_inclusive) if checkpoint else "",
                placeholder="Last chapter (inclusive)",
                id="checkpoint-end",
                type="integer",
            )
            yield Input(value=checkpoint.activity if checkpoint else "normal", placeholder="normal, busy, or quiet", id="checkpoint-activity")
            yield Input(value=checkpoint.notes or "" if checkpoint else "", placeholder="Notes (optional)", id="checkpoint-notes")
            yield Static("Expected memories", classes="section-title")
            with Horizontal(classes="actions"):
                yield Button("Add", id="add-metric")
                yield Button("Edit selected", id="edit-metric")
                yield Button("Remove selected", id="remove-metric")
            yield DataTable(id="checkpoint-metrics")
            yield Label("", id="checkpoint-edit-status")
            with Horizontal(classes="actions"):
                yield Button("Save checkpoint", id="save-checkpoint", variant="primary")
                yield Button("Cancel", id="cancel-checkpoint")

    def on_mount(self) -> None:
        if self.checkpoint is not None:
            self.query_one("#checkpoint-id", Input).disabled = True
        table = self.query_one("#checkpoint-metrics", DataTable)
        table.add_columns("ID", "Type", "Category", "Lifecycle", "Content")
        self.refresh_metrics()

    def refresh_metrics(self) -> None:
        table = self.query_one("#checkpoint-metrics", DataTable)
        table.clear()
        for memory in self.memories:
            table.add_row(memory.id, memory.memory_type, memory.category or "", memory.lifecycle, memory.content)

    def selected_memory(self) -> ExpectedMemory | None:
        table = self.query_one("#checkpoint-metrics", DataTable)
        if table.row_count == 0:
            return None
        memory_id = str(table.get_row_at(table.cursor_row)[0])
        return next(memory for memory in self.memories if memory.id == memory_id)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-checkpoint":
            self.dismiss(None)
        elif event.button.id == "add-metric":
            self.app.push_screen(MetricEditScreen(), self._metric_finished)
        elif event.button.id == "edit-metric":
            memory = self.selected_memory()
            if memory is not None:
                self.app.push_screen(MetricEditScreen(memory), self._metric_finished)
        elif event.button.id == "remove-metric":
            memory = self.selected_memory()
            if memory is not None:
                self.memories = [candidate for candidate in self.memories if candidate.id != memory.id]
                self.refresh_metrics()
        elif event.button.id == "save-checkpoint":
            self.save()

    def _metric_finished(self, memory: ExpectedMemory | None) -> None:
        if memory is None:
            return
        self.memories = [candidate for candidate in self.memories if candidate.id != memory.id]
        self.memories.append(memory)
        self.refresh_metrics()

    def save(self) -> None:
        notes = self.query_one("#checkpoint-notes", Input).value.strip() or None
        try:
            checkpoint = Checkpoint.model_validate(
                {
                    "id": self.query_one("#checkpoint-id", Input).value.strip(),
                    "corpus": self.query_one("#checkpoint-corpus", Input).value.strip(),
                    "chapters": {
                        "start_inclusive": self.query_one("#checkpoint-start", Input).value,
                        "end_inclusive": self.query_one("#checkpoint-end", Input).value,
                    },
                    "activity": self.query_one("#checkpoint-activity", Input).value.strip(),
                    "expected_memories": self.memories,
                    "notes": notes,
                }
            )
            if self.checkpoint is None:
                create_checkpoint(self.workspace, checkpoint)
            else:
                save_checkpoint(self.workspace, checkpoint)
        except (OSError, ValueError) as exc:
            self.query_one("#checkpoint-edit-status", Label).update(str(exc))
            return
        self.dismiss(checkpoint)


class CheckpointScreen(Screen[None]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, workspace: EvalWorkspace) -> None:
        super().__init__()
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="resource"):
            yield Static("Checkpoints", classes="screen-title")
            with Horizontal(classes="actions"):
                yield Button("Create", id="create-checkpoint", variant="primary")
                yield Button("Edit selected", id="edit-checkpoint")
                yield Button("Delete selected", id="delete-checkpoint", variant="error")
                yield Button("Refresh", id="refresh-checkpoints")
            yield Label("", id="checkpoint-status")
            yield DataTable(id="checkpoint-entries")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#checkpoint-entries", DataTable)
        table.add_columns("ID", "Corpus", "Chapters", "Activity", "Expected memories")
        self.refresh_checkpoints()

    def refresh_checkpoints(self) -> None:
        table = self.query_one("#checkpoint-entries", DataTable)
        status = self.query_one("#checkpoint-status", Label)
        table.clear()
        try:
            summaries = discover_checkpoints(self.workspace)
        except (OSError, ValueError) as exc:
            status.update(str(exc))
            return
        for summary in summaries:
            table.add_row(
                summary.id,
                summary.corpus,
                f"{summary.start_chapter}-{summary.end_chapter}",
                summary.activity,
                str(summary.memory_count),
            )
        status.update(f"{len(summaries)} checkpoint(s)")

    def selected_checkpoint(self) -> CheckpointSummary | None:
        table = self.query_one("#checkpoint-entries", DataTable)
        if table.row_count == 0:
            return None
        checkpoint_id = str(table.get_row_at(table.cursor_row)[0])
        return next(summary for summary in discover_checkpoints(self.workspace) if summary.id == checkpoint_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-checkpoints":
            self.refresh_checkpoints()
        elif event.button.id == "create-checkpoint":
            self.app.push_screen(CheckpointEditScreen(self.workspace), self._edit_finished)
        elif event.button.id == "edit-checkpoint":
            summary = self.selected_checkpoint()
            if summary is not None:
                self.app.push_screen(
                    CheckpointEditScreen(self.workspace, load_checkpoint(self.workspace, summary.id)),
                    self._edit_finished,
                )
        elif event.button.id == "delete-checkpoint":
            summary = self.selected_checkpoint()
            if summary is not None:
                self.app.push_screen(
                    ConfirmScreen(f"Delete checkpoint {summary.id}?"),
                    lambda confirmed: self._delete_finished(summary.id, confirmed),
                )

    def _edit_finished(self, checkpoint: Checkpoint | None) -> None:
        if checkpoint is not None:
            self.refresh_checkpoints()
            self.query_one("#checkpoint-status", Label).update(f"Saved {checkpoint.id}")

    def _delete_finished(self, checkpoint_id: str, confirmed: bool) -> None:
        if confirmed:
            try:
                delete_checkpoint(self.workspace, checkpoint_id)
            except (OSError, ValueError) as exc:
                self.query_one("#checkpoint-status", Label).update(str(exc))
                return
            self.refresh_checkpoints()
            self.query_one("#checkpoint-status", Label).update(f"Deleted {checkpoint_id}")


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


class ConfigEditScreen(ModalScreen[RunConfig | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, workspace: EvalWorkspace, config: RunConfig | None = None) -> None:
        super().__init__()
        self.workspace = workspace
        self.config = config
        self.available_toolsets = discover_toolset_names()
        self.toolset_ids = {name: f"config-toolset-{name.replace('_', '-')}" for name in self.available_toolsets}

    def compose(self) -> ComposeResult:
        config = self.config
        execution = config.execution if config else None
        budget = config.budget if config else None
        selected = {toolset.name for toolset in config.agent.toolsets} if config else set()
        with VerticalScroll(classes="dialog", id="config-dialog"):
            yield Static("Edit run config" if config else "Create run config", classes="screen-title")
            yield Input(value=config.id if config else "", placeholder="Config ID", id="config-id")
            yield Input(value=config.change if config else "", placeholder="Change under evaluation", id="config-change")
            yield Input(value=config.corpus if config else "", placeholder="Corpus ID", id="config-corpus")
            yield Input(
                value=str(config.chapters.start_inclusive) if config else "",
                placeholder="First chapter (inclusive)",
                id="config-start",
                type="integer",
            )
            yield Input(
                value=str(config.chapters.end_inclusive) if config else "",
                placeholder="Last chapter (inclusive)",
                id="config-end",
                type="integer",
            )
            yield Input(
                value=", ".join(config.checkpoints) if config else "",
                placeholder="Checkpoint IDs, comma-separated",
                id="config-checkpoints",
            )
            yield Input(
                value=config.agent.profile if config else "",
                placeholder="Agent profile or model preset",
                id="config-profile",
            )
            yield Static("Backend toolsets", classes="section-title")
            for name in self.available_toolsets:
                yield Checkbox(name, value=name in selected, id=self.toolset_ids[name])
            yield Static("Objectives (one per line)", classes="section-title")
            yield TextArea("\n".join(config.objectives) if config else "", id="config-objectives")
            yield Static("Expected side effects (one per line)", classes="section-title")
            yield TextArea(
                "\n".join(config.expected_side_effects) if config else "",
                id="config-side-effects",
            )
            yield Static("Degradation guardrails (one per line)", classes="section-title")
            yield TextArea(
                "\n".join(config.degradation_guardrails) if config else "",
                id="config-guardrails",
            )
            yield Static("Decision rule", classes="section-title")
            yield TextArea(config.decision_rule if config else "", id="config-decision-rule")
            yield Static("Execution", classes="section-title")
            yield Input(
                value=str(execution.replicas) if execution else "1",
                placeholder="Replicas",
                id="config-replicas",
                type="integer",
            )
            yield Input(
                value=str(execution.max_parallel) if execution else "1",
                placeholder="Maximum parallel runs",
                id="config-max-parallel",
                type="integer",
            )
            yield Input(
                value=str(execution.retries_per_chapter) if execution else "0",
                placeholder="Retries per chapter",
                id="config-retries",
                type="integer",
            )
            yield Static("Optional budget", classes="section-title")
            yield Input(
                value=str(budget.max_cost_usd) if budget and budget.max_cost_usd is not None else "",
                placeholder="Maximum cost in USD",
                id="config-max-cost",
                type="number",
            )
            yield Input(
                value=str(budget.max_wall_seconds) if budget and budget.max_wall_seconds is not None else "",
                placeholder="Maximum wall time in seconds",
                id="config-max-wall",
                type="integer",
            )
            yield Label("", id="config-edit-status")
            with Horizontal(classes="actions"):
                yield Button("Save run config", id="save-config", variant="primary")
                yield Button("Cancel", id="cancel-config")

    def on_mount(self) -> None:
        if self.config is not None:
            self.query_one("#config-id", Input).disabled = True

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-config":
            self.dismiss(None)
        elif event.button.id == "save-config":
            self.save()

    def save(self) -> None:
        checkpoint_ids = [
            value.strip()
            for value in self.query_one("#config-checkpoints", Input).value.split(",")
            if value.strip()
        ]
        existing_settings = (
            {toolset.name: toolset.settings for toolset in self.config.agent.toolsets}
            if self.config is not None
            else {}
        )
        selected_toolsets = [
            {"name": name, "settings": existing_settings.get(name, {})}
            for name in self.available_toolsets
            if self.query_one(f"#{self.toolset_ids[name]}", Checkbox).value
        ]
        max_cost = self.query_one("#config-max-cost", Input).value.strip() or None
        max_wall = self.query_one("#config-max-wall", Input).value.strip() or None
        try:
            config = RunConfig.model_validate(
                {
                    "id": self.query_one("#config-id", Input).value.strip(),
                    "change": self.query_one("#config-change", Input).value.strip(),
                    "objectives": _lines(self.query_one("#config-objectives", TextArea).text),
                    "expected_side_effects": _lines(self.query_one("#config-side-effects", TextArea).text),
                    "degradation_guardrails": _lines(self.query_one("#config-guardrails", TextArea).text),
                    "decision_rule": self.query_one("#config-decision-rule", TextArea).text.strip(),
                    "corpus": self.query_one("#config-corpus", Input).value.strip(),
                    "chapters": {
                        "start_inclusive": self.query_one("#config-start", Input).value,
                        "end_inclusive": self.query_one("#config-end", Input).value,
                    },
                    "checkpoints": checkpoint_ids,
                    "agent": {
                        "profile": self.query_one("#config-profile", Input).value.strip(),
                        "toolsets": selected_toolsets,
                    },
                    "execution": {
                        "replicas": self.query_one("#config-replicas", Input).value,
                        "max_parallel": self.query_one("#config-max-parallel", Input).value,
                        "retries_per_chapter": self.query_one("#config-retries", Input).value,
                    },
                    "budget": {"max_cost_usd": max_cost, "max_wall_seconds": max_wall},
                }
            )
            if self.config is None:
                create_run_config(self.workspace, config)
            else:
                save_run_config(self.workspace, config)
        except (OSError, ValueError) as exc:
            self.query_one("#config-edit-status", Label).update(str(exc))
            return
        self.dismiss(config)


class ConfigScreen(Screen[None]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, workspace: EvalWorkspace) -> None:
        super().__init__()
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="resource"):
            yield Static("Run configs", classes="screen-title")
            with Horizontal(classes="actions"):
                yield Button("Create", id="create-config", variant="primary")
                yield Button("Edit selected", id="edit-config")
                yield Button("Delete selected", id="delete-config", variant="error")
                yield Button("Refresh", id="refresh-configs")
            yield Label("", id="config-status")
            yield DataTable(id="config-entries")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#config-entries", DataTable)
        table.add_columns("ID", "Corpus", "Chapters", "Profile", "Toolsets", "Replicas")
        self.refresh_configs()

    def refresh_configs(self) -> None:
        table = self.query_one("#config-entries", DataTable)
        status = self.query_one("#config-status", Label)
        table.clear()
        try:
            summaries = discover_run_configs(self.workspace)
        except (OSError, ValueError) as exc:
            status.update(str(exc))
            return
        for summary in summaries:
            table.add_row(
                summary.id,
                summary.corpus,
                f"{summary.start_chapter}-{summary.end_chapter}",
                summary.profile,
                ", ".join(summary.toolsets),
                str(summary.replicas),
            )
        status.update(f"{len(summaries)} run config(s)")

    def selected_config(self) -> RunConfigSummary | None:
        table = self.query_one("#config-entries", DataTable)
        if table.row_count == 0:
            return None
        config_id = str(table.get_row_at(table.cursor_row)[0])
        return next(summary for summary in discover_run_configs(self.workspace) if summary.id == config_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-configs":
            self.refresh_configs()
        elif event.button.id == "create-config":
            self.app.push_screen(ConfigEditScreen(self.workspace), self._edit_finished)
        elif event.button.id == "edit-config":
            summary = self.selected_config()
            if summary is not None:
                self.app.push_screen(
                    ConfigEditScreen(self.workspace, load_run_config(self.workspace, summary.id)),
                    self._edit_finished,
                )
        elif event.button.id == "delete-config":
            summary = self.selected_config()
            if summary is not None:
                self.app.push_screen(
                    ConfirmScreen(f"Delete run config {summary.id}?"),
                    lambda confirmed: self._delete_finished(summary.id, confirmed),
                )

    def _edit_finished(self, config: RunConfig | None) -> None:
        if config is not None:
            self.refresh_configs()
            self.query_one("#config-status", Label).update(f"Saved {config.id}")

    def _delete_finished(self, config_id: str, confirmed: bool) -> None:
        if confirmed:
            try:
                delete_run_config(self.workspace, config_id)
            except (OSError, ValueError) as exc:
                self.query_one("#config-status", Label).update(str(exc))
                return
            self.refresh_configs()
            self.query_one("#config-status", Label).update(f"Deleted {config_id}")


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
    #checkpoint-entries, #checkpoint-metrics, #config-entries {
        height: 1fr;
        min-height: 6;
    }
    .actions {
        height: auto;
        margin-bottom: 1;
    }
    .actions Button {
        margin-right: 1;
    }
    CorpusImportScreen, CheckpointEditScreen, MetricEditScreen, ConfigEditScreen, ConfirmScreen {
        align: center middle;
    }
    .dialog, #import-dialog {
        width: 72;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    #import-dialog Input {
        margin-bottom: 0;
    }
    #checkpoint-dialog {
        width: 110;
        height: 95%;
    }
    #metric-dialog {
        width: 90;
        max-height: 90%;
    }
    #config-dialog {
        width: 110;
        height: 95%;
    }
    #config-objectives, #config-side-effects, #config-guardrails, #config-decision-rule {
        height: 5;
        margin-bottom: 1;
    }
    #confirm-dialog {
        width: 60;
    }
    .section-title {
        text-style: bold;
        margin-top: 1;
    }
    """

    def __init__(self, workspace: EvalWorkspace) -> None:
        super().__init__()
        self.workspace = workspace

    def on_mount(self) -> None:
        self.install_screen(CorpusScreen(self.workspace), name="corpora")
        self.install_screen(CheckpointScreen(self.workspace), name="checkpoints")
        self.install_screen(ConfigScreen(self.workspace), name="configs")
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
