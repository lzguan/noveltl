from src.main import app


def test_memory_routes_are_exposed_in_openapi() -> None:
    openapi = app.openapi()
    paths = openapi["paths"]

    assert set(paths["/memories/{memoryId}"]) == {"get", "delete"}
    assert set(paths["/memory-groups/{memoryGroupId}/glossary/memories"]) == {"get", "post"}
    assert set(paths["/memory-groups/{memoryGroupId}/glossary/terms"]) == {"get", "post"}
    assert set(paths["/memory-groups/{memoryGroupId}/glossary/terms/{termId}"]) == {"patch", "delete"}


def test_memory_delete_contract_has_no_response_body() -> None:
    operation = app.openapi()["paths"]["/memories/{memoryId}"]["delete"]

    assert set(operation["responses"]) == {"204", "404", "422"}
    assert "content" not in operation["responses"]["204"]
