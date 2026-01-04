from typing import Dict, List, Tuple, TypedDict, cast

from ..schemas import CluenerModelParams, NERModelParamsBase
from ...labels.schemas import Label
from .utils import *
from .interfaces import *

class CluenerTokenizer(Tokenizer):
    def __init__(self, tokenizer):
        if tokenizer is None:
            raise Exception("Cluener pipeline tokenizer is None.")
        self.tokenizer = tokenizer

    def tokenize(self, text: str) -> List[str]:
        return self.tokenizer.tokenize(text)
    
    def tokenize_words(self, text: str) -> List[Tuple[str, int]]:
        return [(t, 1) for t in self.tokenize(text)]

class CluenerRawNERResult(TypedDict):
    word : str
    score : float
    start : int
    end : int
    entity_group : str

class CluenerModel(NERModel):
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.model_name = 'uer/roberta-base-finetuned-cluener2020-chinese' # maybe change this later
        self.is_deterministic = True
        self.tokenizer = CluenerTokenizer(pipeline.tokenizer)
    
    def predict(self, text: str, params: CluenerModelParams) -> Tuple[List[Label], List[CluenerRawNERResult]]:
        chunks = chunk_text(text, params.separators, self.tokenizer, params.chunk_size, force_chunk=params.force_chunk)
        ret = []
        err = []
        for txt, start in chunks:
            result : List[CluenerRawNERResult] = cast(List[CluenerRawNERResult], self.pipeline(txt))
            for label in result:
                label['word'] = label['word'].replace(" ", "")
                label['start'] = label['start'] + start
                label['end'] = label['end'] + start
                if self.normalize(text[label['start']:label['end']]) != label['word']:
                    err.append(label)
                else:
                    ret.append(Label(
                        label_word=label["word"],
                        label_start=label["start"],
                        label_end=label["end"],
                        label_score=label["score"],
                        label_entity_group=label["entity_group"], 
                        label_dirty=False
                    ))
        return ret, err
    
    def get_tokenizer(self) -> Tokenizer:
        return self.tokenizer
    
    def normalize(self, text: str) -> str:
        return text.lower()
    
    def validate(self, params: Dict[str, str | int | float | bool]) -> NERModelParamsBase:
        return CluenerModelParams.model_validate(params, context={'skip_default_values' : True})

class Cluener:
    
    def __init__(self):
        from transformers import pipeline # type : ignore

        self.pipeline = pipeline(
            'token-classification',
            model='uer/roberta-base-finetuned-cluener2020-chinese',
            aggregation_strategy="simple"
        )
        self.model = CluenerModel(self.pipeline)

