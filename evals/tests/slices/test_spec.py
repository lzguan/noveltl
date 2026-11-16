import ast
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from evals.slices.spec import GroupCut, Slice

GROUP = uuid4()
NOVEL = uuid4()


def _group_cut(group: dict[str, object], horizon: int | None = 20) -> GroupCut:
    return Slice.model_validate({"horizon": horizon, "groups": [{"group_id": GROUP, **group}]}).group_cuts()[GROUP]


def test_kinds_inherit_the_group_horizon_which_inherits_the_slice_horizon() -> None:
    assert _group_cut({}) == GroupCut(20, 20, 20, 20)
    assert _group_cut({"horizon": 40, "memories": 30}) == GroupCut(40, 40, 30, 40)


def test_null_means_no_cut_and_false_excludes_a_kind() -> None:
    assert _group_cut({"terms": None, "conventions": False}) == GroupCut(None, 20, 20, False)
    assert _group_cut({"horizon": None}, horizon=20) == GroupCut(None, None, None, None)


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (False, False)])
def test_zero_and_false_stay_distinct(value: object, expected: object) -> None:
    cut = _group_cut({"terms": None, "conventions": value})
    assert cut.conventions == expected
    assert type(cut.conventions) is type(expected)


def test_novels_inherit_the_slice_horizon_unless_set() -> None:
    spec = Slice.model_validate({"horizon": 20, "novels": [{"novel_id": NOVEL}, {"novel_id": GROUP, "horizon": None}]})
    assert spec.novel_cuts() == {NOVEL: 20, GROUP: None}


@pytest.mark.parametrize(
    "group",
    [
        {"terms": 10},
        {"terms": 20, "term_translations": None},
        {"terms": False, "term_translations": False},
    ],
)
def test_memories_and_translations_may_not_outlast_terms(group: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="must not extend past terms"):
        _group_cut(group)


def test_dependent_kinds_may_stop_before_terms() -> None:
    assert _group_cut({"terms": None, "term_translations": 5, "memories": False}) == GroupCut(None, 5, False, 20)


@pytest.mark.parametrize("key", ["novels", "groups"])
def test_repeated_parts_are_rejected(key: str) -> None:
    field = "novel_id" if key == "novels" else "group_id"
    with pytest.raises(ValidationError, match="may appear once"):
        Slice.model_validate({key: [{field: GROUP}, {field: GROUP}]})


@pytest.mark.parametrize(
    "spec",
    [
        {"groups": [{"group_id": str(GROUP), "term_translation": 5}]},
        {"horizon": -1},
        {"groups": [{"group_id": str(GROUP), "horizon": False}]},
        {"groups": [{"group_id": str(GROUP), "conventions": True}]},
        {"horizon": "20"},
    ],
)
def test_malformed_specs_are_rejected(spec: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Slice.model_validate(spec)


def test_unset_fields_are_left_out_when_dumped() -> None:
    spec = Slice.model_validate({"horizon": 20, "groups": [{"group_id": GROUP, "conventions": None}]})
    assert spec.model_dump(mode="json")["groups"] == [{"group_id": str(GROUP), "conventions": None}]
    assert Slice.model_validate(spec.model_dump(mode="json")) == spec


def test_slices_imports_nothing_else_from_evals() -> None:
    package = Path(__file__).parents[2] / "src/evals/slices"
    for path in package.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom) and node.level == 0
                else []
            )
            for name in names:
                assert not (name == "evals" or name.startswith("evals.")) or name.startswith("evals.slices"), (
                    f"{path.name} imports {name}"
                )
