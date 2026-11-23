from collections.abc import AsyncIterable, AsyncIterator

from src.files.async_storage import AsyncObjectStore
from src.lib.aiter import achain
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.common.inputs import StageTypes, batch_chapter_ids, resolve_inputs, select_streams
from src.translations.models import TranslationStage
from src.translations.records import TranslationRecord
from src.translations.validation import validate_output_records


async def output_records(
    context: ActionTaskContext,
    store: AsyncObjectStore,
    stage: TranslationStage,
    produced: AsyncIterable[TranslationRecord],
    types: StageTypes,
) -> AsyncIterator[TranslationRecord]:
    kept = select_streams(
        resolve_inputs(context, store, stage, types.before),
        types.before.keys() - types.signature.outputs.keys() - types.signature.drops,
    )
    records = validate_output_records(
        achain(kept, produced), chapter_ids=await batch_chapter_ids(context, stage), output_type=types.after
    )
    async for record in records:
        yield record
