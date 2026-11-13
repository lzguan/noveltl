from collections.abc import Iterable, Iterator
from itertools import chain

from src.files.storage import ObjectStore
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.common.inputs import StageTypes, batch_chapter_ids, resolve_inputs, select_streams
from src.translations.models import TranslationStage
from src.translations.records import TranslationRecord
from src.translations.validation import validate_output_records


def output_records(
    context: ActionTaskContext,
    store: ObjectStore,
    stage: TranslationStage,
    produced: Iterable[TranslationRecord],
    types: StageTypes,
) -> Iterator[TranslationRecord]:
    kept = select_streams(
        resolve_inputs(context, store, stage, types.before),
        types.before.keys() - types.signature.outputs.keys() - types.signature.drops,
    )
    return validate_output_records(
        chain(kept, produced), chapter_ids=batch_chapter_ids(context, stage), output_type=types.after
    )
