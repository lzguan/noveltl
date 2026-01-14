from typing import Annotated, Any

from pydantic import BeforeValidator

from .constants import MAX_PARAMS_SIZE_BYTES


def is_size_small(value : dict[str, Any]) -> dict[str, Any]:
    if len(str(value)) > MAX_PARAMS_SIZE_BYTES:
        raise ValueError("Value too long.")
    return value

SmallDict = Annotated[dict[str, Any], BeforeValidator(is_size_small)]
