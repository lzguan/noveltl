from typing import Any

from pydantic import BaseModel, ValidationInfo, model_validator


class SkipDefaultModel(BaseModel):

    @model_validator(mode='before')
    @classmethod
    def validate_skip_defaults(cls, data : Any, info : ValidationInfo) -> Any:
        if info.context and info.context.get('skip_default_values'):
            if not isinstance(data, dict):
                raise ValueError("Data is not a dict.")
            fields_with_defaults = {k for k, v in cls.model_fields.items() if not v.is_required()}
            keys_set = {k for k, _ in data.items()} # pyright: ignore[reportUnknownVariableType]
            missing = fields_with_defaults - keys_set
            if len(missing) > 0:
                raise ValueError(f"Fields not set: {missing}")

        return data # pyright: ignore[reportUnknownVariableType]
