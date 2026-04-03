from typing import Any, Protocol, TypedDict, cast

from ...labels.schemas import LabelBase
from ..schemas import CluenerModelParams, NERModelParamsBase
from .interfaces import NERModel, Tokenizer
from .utils import chunk_text


class TokenizerType(Protocol):
    def tokenize(self, text: str) -> list[str]: ...


class PipelineType(Protocol):
    tokenizer: TokenizerType

    def __call__(self, text: str) -> list[dict[str, Any]]: ...


class CluenerTokenizer(Tokenizer):
    def __init__(self, tokenizer: TokenizerType):
        self.tokenizer = tokenizer

    def tokenize(self, text: str) -> list[str]:
        return self.tokenizer.tokenize(text)

    def tokenize_words(self, text: str) -> list[tuple[str, int]]:
        return [(t, 1) for t in self.tokenize(text)]


class CluenerRawNERResult(TypedDict):
    word: str
    score: float
    start: int
    end: int
    entity_group: str


class CluenerModel(NERModel[CluenerModelParams]):
    def __init__(self, pipeline: PipelineType):
        self.pipeline = pipeline
        self.model_name = "uer/roberta-base-finetuned-cluener2020-chinese"  # maybe change this later
        self.is_deterministic = True
        self.tokenizer = CluenerTokenizer(pipeline.tokenizer)

    def predict(self, text: str, params: CluenerModelParams) -> tuple[list[LabelBase], list[CluenerRawNERResult]]:
        chunks = chunk_text(text, params.separators, self.tokenizer, params.chunk_size, force_chunk=params.force_chunk)
        ret: list[LabelBase] = []
        err: list[CluenerRawNERResult] = []
        for txt, start in chunks:
            result: list[CluenerRawNERResult] = cast(list[CluenerRawNERResult], self.pipeline(txt))
            for label in result:
                label["word"] = label["word"].replace(" ", "")
                label["start"] = label["start"] + start
                label["end"] = label["end"] + start
                if self.normalize(text[label["start"] : label["end"]]) != label["word"]:
                    err.append(label)
                else:
                    ret.append(
                        LabelBase(
                            label_word=label["word"],
                            label_start=label["start"],
                            label_end=label["end"],
                            label_score=label["score"],
                            label_entity_group=label["entity_group"],
                            label_dirty=False,
                        )
                    )
        return ret, err

    def get_tokenizer(self) -> Tokenizer:
        return self.tokenizer

    def normalize(self, text: str) -> str:
        return text.lower()

    def validate(self, params: dict[str, str | int | float | bool]) -> NERModelParamsBase:
        return CluenerModelParams.model_validate(params, context={"skip_default_values": True})


class Cluener:
    def __init__(self):
        from transformers import pipeline  # type : ignore

        self.pipeline = pipeline(
            "token-classification",
            model="uer/roberta-base-finetuned-cluener2020-chinese",
            aggregation_strategy="simple",
        )
        self.model: NERModel[CluenerModelParams] = CluenerModel(self.pipeline)  # pyright: ignore[reportArgumentType]
