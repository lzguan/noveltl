"""Model provider configuration shared by every memory-agent factory."""

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer, OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

from src.config import inception_settings
from src.memory.agent.types import ModelName

MERCURY_PROFILE = OpenAIModelProfile(
    json_schema_transformer=OpenAIJsonSchemaTransformer,
    supports_json_schema_output=True,  # response_format json_schema returned valid JSON
    supports_json_object_output=True,  # json_object mode likewise
    supports_thinking=True,  # REQUIRED - see below
    openai_supports_strict_tool_definition=True,
    openai_supports_tool_choice_required=True,  # "required" and named forcing both accepted
    openai_reasoning_enabled_by_default=True,  # omitting the param spends ~200-260 reasoning tokens
    openai_chat_supports_multiple_system_messages=True,
    context_window=260_000,
)


def model_configuration(model_name: ModelName) -> tuple[Model | str, OpenAIChatModelSettings]:
    """Resolve provider configuration shared by the agent factories."""
    model: Model | str
    model_settings: OpenAIChatModelSettings
    if model_name == "deepseek:deepseek-v4-flash-none":
        model = "deepseek:deepseek-v4-flash"
        model_settings = {"extra_body": {"thinking": {"type": "disabled"}}}
    elif model_name == "deepseek:deepseek-v4-flash-low":
        model = "deepseek:deepseek-v4-flash"
        model_settings = {"thinking": "low"}
    elif model_name == "inception:mercury-2.5-low":
        model = OpenAIChatModel(
            "mercury-2.5",
            provider=OpenAIProvider(
                api_key=inception_settings.INCEPTION_API_KEY, base_url=inception_settings.INCEPTION_API_URL
            ),
            profile=MERCURY_PROFILE,
        )
        model_settings = {"thinking": "low"}
    else:
        raise ValueError(f"Unknown model name {model_name!r}")
    return model, model_settings
