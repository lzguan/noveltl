import asyncio
import json
from pathlib import Path

from textual.widgets import DataTable, Input

from agent_evals.storage import EvalWorkspace
from agent_evals.tui import AgentEvalApp, CorpusImportScreen, CorpusScreen, HomeScreen


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
