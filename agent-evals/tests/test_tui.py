import asyncio
import json
from pathlib import Path

from textual.widgets import DataTable, Input

from agent_evals.checkpoints import load_checkpoint
from agent_evals.corpora import CorpusImportSpec, import_flat_export
from agent_evals.storage import EvalWorkspace
from agent_evals.tui import (
    AgentEvalApp,
    CheckpointEditScreen,
    CheckpointScreen,
    CorpusImportScreen,
    CorpusScreen,
    HomeScreen,
    MetricEditScreen,
)


def test_corpus_import_workflow_displays_imported_corpus(tmp_path: Path) -> None:
    source = tmp_path / "novel.json"
    source.write_text(
        json.dumps(
            {
                "chapters": [
                    {
                        "chapterNum": 1,
                        "chapterTitle": "开端",
                        "chapterIsPublic": False,
                        "chapterContentText": "林渊醒来。",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    workspace = EvalWorkspace(tmp_path / "evals")
    workspace.ensure()

    async def exercise() -> None:
        app = AgentEvalApp(workspace)
        async with app.run_test() as pilot:
            assert isinstance(app.screen, HomeScreen)
            await pilot.click("#corpora")
            assert isinstance(app.screen, CorpusScreen)
            await pilot.click("#open-import")
            assert isinstance(app.screen, CorpusImportScreen)
            app.screen.query_one("#import-source", Input).value = str(source)
            app.screen.query_one("#import-id", Input).value = "cn-xianxia-001"
            app.screen.query_one("#import-title", Input).value = "Private evaluation novel"
            app.screen.query_one("#import-language", Input).value = "zh"
            await pilot.click("#confirm-import")
            for _ in range(50):
                if isinstance(app.screen, CorpusScreen):
                    break
                await pilot.pause(0.1)
            assert isinstance(app.screen, CorpusScreen)
            table = app.screen.query_one("#corpus-entries", DataTable)
            assert table.row_count == 1
            assert table.get_row_at(0)[0] == "cn-xianxia-001"

    asyncio.run(exercise())


def test_checkpoint_editor_creates_checkpoint_with_expected_memory(tmp_path: Path) -> None:
    source = tmp_path / "novel.json"
    source.write_text(
        json.dumps(
            {
                "chapters": [
                    {
                        "chapterNum": 1,
                        "chapterTitle": "开端",
                        "chapterContentText": "林渊醒来。",
                    }
                ]
            },
            ensure_ascii=False,
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

    async def exercise() -> None:
        app = AgentEvalApp(workspace)
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.click("#checkpoints")
            assert isinstance(app.screen, CheckpointScreen)
            await pilot.click("#create-checkpoint")
            assert isinstance(app.screen, CheckpointEditScreen)
            app.screen.query_one("#checkpoint-id", Input).value = "opening"
            app.screen.query_one("#checkpoint-corpus", Input).value = "test-novel"
            app.screen.query_one("#checkpoint-start", Input).value = "1"
            app.screen.query_one("#checkpoint-end", Input).value = "1"
            await pilot.click("#add-metric")
            assert isinstance(app.screen, MetricEditScreen)
            app.screen.query_one("#metric-id", Input).value = "identity"
            app.screen.query_one("#metric-type", Input).value = "fact"
            app.screen.query_one("#metric-category", Input).value = "identity"
            app.screen.query_one("#metric-terms", Input).value = "林渊"
            app.screen.query_one("#metric-content", Input).value = "The protagonist awakens."
            await pilot.click("#apply-metric")
            assert isinstance(app.screen, CheckpointEditScreen)
            await pilot.click("#save-checkpoint")
            assert isinstance(app.screen, CheckpointScreen)

    asyncio.run(exercise())
    checkpoint = load_checkpoint(workspace, "opening", validate_context=True)
    assert checkpoint.expected_memories[0].id == "identity"
    assert checkpoint.expected_memories[0].terms == ["林渊"]
