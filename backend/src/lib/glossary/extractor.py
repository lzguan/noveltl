# Class for extracting named entities from text
from typing import Protocol


class Tokenizer(Protocol):
    def tokenize(self, text : str) -> list[str]:
        """Returns a list of token strings"""
        ...

class NERModel(Protocol):
    def predict(self, text : str) -> list[dict]:
        """Returns a list of named entities in text in the format 
            {
                'entity_group' : ...
                'score' : ...
                'word' : ...
                'start' : ...
                'end' : ...
            }
        """
        ...

    def get_tokenizer(self) -> Tokenizer:
        ...

class Extractor:
    def __init__(self, model : NERModel, chunk_size : int, sentence_sep = None):
        self.model = model
        self.chunk_size = chunk_size
        self.tokenizer = model.get_tokenizer()
        self.sentence_sep = sentence_sep

    def chunk_text(self, text : str) -> list[str]:
        """Separates text into chunks of size at most chunk_size
            Chunks will only be separated at newlines
        Args:
            text: text to chunk
        """
        lines = text.split("\n")
        chunks = []
        cur_chunk = ""
        cur_chunk_size = 0
        for line in lines:
            t_line = self.tokenizer.tokenize(line)
            if len(t_line) > self.chunk_size:
                if not self.sentence_sep:
                    raise Exception("Line too long")
                if cur_chunk_size > 0:
                    chunks.append(cur_chunk)
                    cur_chunk = ""
                    cur_chunk_size = 0
                sentences = [sentence + self.sentence_sep for sentence in line.split(self.sentence_sep) if sentence]
                # same logic as splitting lines but with sentences
                for sentence in sentences:
                    t_sentence = self.tokenizer.tokenize(sentence)
                    if len(t_sentence) > self.chunk_size:
                        raise Exception("Sentence too long")
                    if cur_chunk_size + len(t_sentence) > self.chunk_size:
                        chunks.append(cur_chunk)
                        cur_chunk = ""
                        cur_chunk_size = 0
                    cur_chunk = cur_chunk + sentence
                    cur_chunk_size = cur_chunk_size + len(t_sentence)
                if cur_chunk:
                    chunks.append(cur_chunk)
                    cur_chunk = ""
                    cur_chunk_size = 0
                continue
            if cur_chunk_size + len(t_line) > self.chunk_size:
                chunks.append(cur_chunk)
                cur_chunk = ""
                cur_chunk_size = 0
            if cur_chunk:
                cur_chunk = cur_chunk + '\n'
            cur_chunk = cur_chunk + line
            cur_chunk_size = cur_chunk_size + len(t_line)
        if cur_chunk:
            chunks.append(cur_chunk)
        return chunks

    def extract_named_entities(self, text : str) -> list[dict]:
        """Returns a list of named entities in text in the format
            {
                'entity_group' : ...
                'score' : ...
                'word' : ...
                'start' : ...
                'end' : ...
            }
        
        Args:
            text: text to perform extraction on
        """
        chunks = self.chunk_text(text)
        all_entities = []
        current_search_pos = 0
        for chunk in chunks:
            chunk_entities = self.model.predict(chunk)
            chunk_offset = text.find(chunk, current_search_pos)

            for entity in chunk_entities:
                entity['start'] = entity['start'] + chunk_offset
                entity['end'] = entity['end'] + chunk_offset
            all_entities.extend(chunk_entities)
        return all_entities

class HuggingFaceTokenizer:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def tokenize(self, text : str) -> list[str]:
        return self.tokenizer.tokenize(text)

class HuggingFaceModel:
    def __init__(self, pipeline):
        self.pipeline = pipeline

    def predict(self, text : str) -> list[dict]:
        return self.pipeline(text)

    def get_tokenizer(self) -> Tokenizer:
        return HuggingFaceTokenizer(self.pipeline.tokenizer)
