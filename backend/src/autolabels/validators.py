from typing import Annotated, Dict, Any
from pydantic import BeforeValidator
from .constants import MAX_PARAMS_SIZE_BYTES

def is_size_small(value : Dict[str, Any]) -> Dict[str, Any]:
    if len(str(value)) > MAX_PARAMS_SIZE_BYTES:
        raise ValueError("Value too long.")
    return value

SmallDict = Annotated[Dict[str, Any], BeforeValidator(is_size_small)]