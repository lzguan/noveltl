from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.translations.metadata import check_pipeline
from src.translations.pipeline_schemas import TranslationPipelineCheck
from src.translations.router import router
from src.translations.schemas import MAX_STAGES, TranslationJobCreateRequest, TranslationJobDraft

NOVEL_ID = "00000000-0000-0000-0000-000000000001"
MEMORIES = {"memories": {"type": "memories", "memoryGroupId": "00000000-0000-0000-0000-000000000002"}}


def draft(inputs: dict, actions: list[str]) -> dict:
    return {
        "novelId": NOVEL_ID,
        "config": {"batchSize": 10},
        "inputs": inputs,
        "stages": [{"action": action} for action in actions],
    }


def check(inputs: dict, actions: list[str]) -> TranslationPipelineCheck:
    return check_pipeline(TranslationJobDraft.model_validate(draft(inputs, actions)))


def links(result: TranslationPipelineCheck, index: int) -> dict[str, tuple[str, int | None]]:
    return {port.stream: (port.link, port.source) for port in result.stages[index].inputs}


def addable(result: TranslationPipelineCheck) -> dict[str, str | None]:
    return {action.action: action.warning for action in result.addable}


def test_the_loader_is_the_source_and_an_empty_draft_ends_at_its_outputs() -> None:
    result = check(MEMORIES, [])
    assert [stage.action for stage in result.stages] == ["load_inputs"]
    assert result.stages[0].inputs == []
    assert [(port.stream, port.type) for port in result.stages[0].outputs] == [
        ("chapter", "chapter"),
        ("memories", "memories"),
    ]
    assert [(end.stream, end.type, end.source) for end in result.ends] == [
        ("chapter", "chapter", 0),
        ("memories", "memories", 0),
    ]
    assert addable(result) == {"translate": None, "prune_memories": None}
    assert addable(check({}, [])) == {"translate": None, "prune_memories": "requires memories"}


def test_each_port_links_to_the_stage_that_last_wrote_its_stream() -> None:
    result = check(MEMORIES, ["prune_memories", "translate", "translate"])
    assert [stage.warning for stage in result.stages] == [None] * 4
    # Pruning reads the loader's streams and rewrites memories only.
    assert links(result, 1) == {"chapter": ("linked", 0), "memories": ("linked", 0)}
    assert [port.stream for port in result.stages[1].outputs] == ["memories"]
    # The first translation skips past pruning for the chapter; the second reads the first's.
    assert links(result, 2) == {"chapter": ("linked", 0), "memories": ("linked", 1)}
    assert links(result, 3) == {"chapter": ("linked", 2), "memories": ("linked", 1)}
    assert [(end.stream, end.source) for end in result.ends] == [("chapter", 3), ("memories", 1)]
    chapter, memories = result.stages[2].inputs
    assert (chapter.optional, memories.optional) == (False, True)
    assert chapter.source_type == "chapter" and not chapter.drops


def test_new_loader_outputs_pass_through_stages_without_becoming_stage_inputs() -> None:
    inputs = {
        name: {"type": name, "memoryGroupId": MEMORIES["memories"]["memoryGroupId"]}
        for name in ("terms", "conventions")
    }
    result = check(inputs, ["translate"])
    assert [(port.stream, port.type) for port in result.stages[0].outputs] == [
        ("chapter", "chapter"),
        ("terms", "terms"),
        ("conventions", "conventions"),
    ]
    assert [(end.stream, end.source) for end in result.ends] == [("chapter", 1), ("terms", 0), ("conventions", 0)]
    assert links(result, 1) == {"chapter": ("linked", 0), "memories": ("absent", None)}


def test_an_optional_port_without_a_producer_is_absent_not_broken() -> None:
    result = check({}, ["translate"])
    assert links(result, 1) == {"chapter": ("linked", 0), "memories": ("absent", None)}
    assert result.stages[1].warning is None
    assert [end.stream for end in result.ends] == ["chapter"]


def test_a_stage_with_a_broken_port_is_warned_about_and_feeds_nothing() -> None:
    result = check({}, ["translate", "prune_memories", "load_inputs", "translate"])
    assert [stage.warning for stage in result.stages] == [None, None, "requires memories", "unknown action", None]
    assert links(result, 2) == {"chapter": ("linked", 1), "memories": ("broken", None)}
    # The broken stage still shows its ports, but nothing below is fed by it.
    assert [port.stream for port in result.stages[2].outputs] == ["memories"]
    assert links(result, 4) == {"chapter": ("linked", 1), "memories": ("absent", None)}
    assert [(end.stream, end.source) for end in result.ends] == [("chapter", 4)]
    assert addable(result) == {"translate": None, "prune_memories": "requires memories"}


def test_a_full_pipeline_accepts_no_more_stages() -> None:
    assert set(addable(check({}, ["translate"] * MAX_STAGES)).values()) == {
        f"a job can have at most {MAX_STAGES} stages"
    }


def test_a_draft_is_a_creation_request_that_may_have_no_stages() -> None:
    complete = draft(MEMORIES, ["translate"])
    complete["stages"][0]["config"] = {"model": "qwen-plus"}
    assert TranslationJobCreateRequest.model_validate(complete).model_dump() == (
        TranslationJobDraft.model_validate(complete).model_dump()
    )
    assert issubclass(TranslationJobCreateRequest, TranslationJobDraft)


def test_route_checks_drafts_for_authenticated_users() -> None:
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.post("/translation-jobs/check", json=draft({}, [])).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: User()
        response = client.post("/translation-jobs/check", json=draft({}, ["prune_memories"]))
        assert response.status_code == 200
        assert response.json() == {
            "stages": [
                {
                    "action": "load_inputs",
                    "inputs": [],
                    "outputs": [{"stream": "chapter", "type": "chapter"}],
                    "warning": None,
                },
                {
                    "action": "prune_memories",
                    "inputs": [
                        {
                            "stream": "chapter",
                            "type": "chapter",
                            "optional": False,
                            "drops": False,
                            "link": "linked",
                            "source": 0,
                            "sourceType": "chapter",
                        },
                        {
                            "stream": "memories",
                            "type": "memories",
                            "optional": False,
                            "drops": False,
                            "link": "broken",
                            "source": None,
                            "sourceType": None,
                        },
                    ],
                    "outputs": [{"stream": "memories", "type": "memories"}],
                    "warning": "requires memories",
                },
            ],
            "ends": [{"stream": "chapter", "type": "chapter", "source": 0}],
            "addable": [
                {"action": "translate", "warning": None},
                {"action": "prune_memories", "warning": "requires memories"},
            ],
        }
        # A stream must be named after its type, in drafts and creation requests alike.
        misnamed = draft({"side": MEMORIES["memories"]}, [])
        assert client.post("/translation-jobs/check", json=misnamed).status_code == 422
        assert (
            client.post("/translation-jobs", json=misnamed | {"stages": [{"action": "translate"}]}).status_code == 422
        )
        assert client.post("/translation-jobs", json=draft({}, [])).status_code == 422
