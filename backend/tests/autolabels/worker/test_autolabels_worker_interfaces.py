"""
Todo: Refactor AI generated tests.
"""


import pytest

from src.autolabels.constants import SepPriority
from src.autolabels.exceptions import ChunkTooLargeException, TokenDoesNotExistException
from src.autolabels.worker.interfaces import Tokenizer
from src.autolabels.worker.utils import _chunk_blocks, _chunk_paragraph, chunk_text


def test_chunk_blocks():
    separators = {
        '.': SepPriority.HIGH,
        ',': SepPriority.MED,
        ' ': SepPriority.LOW
    }
    text = "Hello, world. This is a test"
    chunks = list(_chunk_blocks(text, separators))
    expected_chunks = [
        ("Hello,", 0, SepPriority.MED),
        (" ", 6, SepPriority.LOW),
        ("world.", 7, SepPriority.HIGH),
        (" ", 13, SepPriority.LOW),
        ("This ", 14, SepPriority.LOW),
        ("is ", 19, SepPriority.LOW),
        ("a ", 22, SepPriority.LOW),
        ("test", 24, None)
    ]
    assert chunks == expected_chunks

    text2 = "NoSeparatorsHere"
    chunks2 = list(_chunk_blocks(text2, separators))
    expected_chunks2 = [
        ("NoSeparatorsHere", 0, None)
    ]
    assert chunks2 == expected_chunks2

class TokenizerTestWords(Tokenizer):
    def tokenize(self, text: str) -> list[str]:
        return text.strip().split(' ')

    def tokenize_words(self, text: str) -> list[tuple[str, int]]:
        return [(word, 1) for word in self.tokenize(text)]

class TokenizerTestWordsMerge(Tokenizer):
    def tokenize(self, text: str) -> list[str]:
        split_text = text.strip().split(' ')
        merge_text : list[str] = []
        for txt in split_text:
            if len(merge_text) > 0 and merge_text[-1] in ['a', 'the']:
                merge_text[-1] = merge_text[-1] + ' ' + txt
            else:
                merge_text.append(txt)
        return merge_text

    def tokenize_words(self, text: str) -> list[tuple[str, int]]:
        return [(word, word.count(' ') + 1) for word in self.tokenize(text)]

def test_SepPriority_enum():
    assert SepPriority.HIGH < SepPriority.MED
    assert SepPriority.MED < SepPriority.LOW
    assert SepPriority.HIGH < SepPriority.LOW

def test_tokenizer_tokenize_simple():
    tokenizer1 = TokenizerTestWords()
    text = "This is a test."
    tokens = tokenizer1.tokenize(text)
    assert tokens == ["This", "is", "a", "test."]

    text2 = "Word1\tWord2\nWord3 Word4 Word5"
    tokens_words_2 = tokenizer1.tokenize_words(text2)
    assert tokens_words_2 == [("Word1\tWord2\nWord3", 1), ("Word4", 1), ("Word5", 1)]

    tokenizer2 = TokenizerTestWordsMerge()
    tokens_3 = tokenizer2.tokenize(text)
    assert tokens_3 == ["This", "is", "a test."]
    tokens_words_3 = tokenizer2.tokenize_words(text)
    assert tokens_words_3 == [("This", 1), ("is", 1), ("a test.", 2)]

    text3 = "the quick brown fox jumps over the lazy dog"
    tokens_4 = tokenizer2.tokenize(text3)
    assert tokens_4 == ["the quick", "brown", "fox", "jumps", "over", "the lazy", "dog"]
    tokens_words_4 = tokenizer2.tokenize_words(text3)
    assert tokens_words_4 == [("the quick", 2), ("brown", 1), ("fox", 1), ("jumps", 1), ("over", 1), ("the lazy", 2), ("dog", 1)]


def test_chunk_paragraph_behaviour():
    tokenizer1 = TokenizerTestWords()
    text = "This is a test paragraph to check chunking behavior."
    max_chunk_size = 5  # in tokens
    chunks = list(_chunk_paragraph(text, max_chunk_size, 0, tokenizer1.tokenize_words(text)))
    chunks_text = [chunk for chunk, _ in chunks]
    assert text == ''.join(chunks_text)
    assert all(chunk == text[start:start+len(chunk)] for chunk, start in chunks)

    tokenizer2 = TokenizerTestWordsMerge()
    text2 = "the quick brown fox jumps over the lazy dog"
    max_chunk_size2 = 4  # in tokens
    chunks2 = list(_chunk_paragraph(text2, max_chunk_size2, 0, tokenizer2.tokenize_words(text2)))
    chunks_text2 = [chunk for chunk, _ in chunks2]
    assert text2 == ''.join(chunks_text2)
    assert all(chunk == text2[start:start+len(chunk)] for chunk, start in chunks2)

def test_chunk_text_basic():
    tokenizer1 = TokenizerTestWords()
    text = "Hello, world. This is a test"
    separators = {
        '.': SepPriority.HIGH,
        ',': SepPriority.MED,
    }
    chunks = list(chunk_text(text, separators, tokenizer1, max_chunk_size=4, force_chunk=False))
    chunks_text = [chunk for chunk, _ in chunks]
    assert text == ''.join(chunks_text)
    assert all(chunk == text[start:start+len(chunk)] for chunk, start in chunks)

    tokenizer2 = TokenizerTestWordsMerge()
    text2 = "the quick brown fox jumps over the lazy dog"
    separators2 = {
        '.': SepPriority.HIGH,
        ',': SepPriority.MED
    }
    with pytest.raises(ChunkTooLargeException):
        chunks_2 = list(chunk_text(text2, separators2, tokenizer2, max_chunk_size=5, force_chunk=False))

    chunks_2 = list(chunk_text(text2, separators2, tokenizer2, max_chunk_size=5, force_chunk=True))
    assert ''.join(chunk for chunk, _ in chunks_2) == text2
    assert all(chunk == text2[start:start+len(chunk)] for chunk, start in chunks_2)

class TokenizerTestChars(Tokenizer):
    def tokenize(self, text: str) -> list[str]:
        return list(text)

    def tokenize_words(self, text: str) -> list[tuple[str, int]]:
        return [(c, 1) for c in text]

def test_chunk_text_SepPriority():
    separators = {
        '\n': SepPriority.HIGH,
        '.': SepPriority.MED,
        ',': SepPriority.LOW
    }
    tokenizer = TokenizerTestChars()
    text = "a,b\nc,"
    chunks = list(chunk_text(text, separators, tokenizer, max_chunk_size=5, force_chunk=True))

    assert ''.join(chunk for chunk, _ in chunks) == text
    assert all(chunk == text[start:start+len(chunk)] for chunk, start in chunks)
    assert len(chunks) == 2
    assert chunks[0][0] == "a,b\n"
    assert chunks[1][0] == "c,"

    text2 = "a\nb,c.d,e"
    chunks2 = list(chunk_text(text2, separators, tokenizer, max_chunk_size=6, force_chunk=True))
    assert ''.join(chunk for chunk, _ in chunks2) == text2
    assert len(chunks2) == 3
    assert chunks2[0][0] == "a\n"
    assert chunks2[1][0] == "b,c."
    assert chunks2[2][0] == "d,e"

def test_chunk_text_massive_paragraph():
    separators = {' ': SepPriority.LOW}
    text = "Hi MassiveBlock"
    tokenizer = TokenizerTestChars()

    chunks = list(chunk_text(text, separators, tokenizer, max_chunk_size=5, force_chunk=True))

    assert chunks[0][0] == "Hi "
    joined_result = "".join(c[0] for c in chunks)
    assert joined_result == text

def test_chunk_text_no_valid_separator():
    separators = {'.': SepPriority.HIGH}
    text = "ABCDEF"
    tokenizer = TokenizerTestChars()

    with pytest.raises(ChunkTooLargeException):
        list(chunk_text(text, separators, tokenizer, max_chunk_size=3, force_chunk=False))

    chunks = list(chunk_text(text, separators, tokenizer, max_chunk_size=3, force_chunk=True))

    assert chunks[0][0] == "ABC"
    assert chunks[1][0] == "DEF"
    assert "".join(c[0] for c in chunks) == text

class TokenizerTestWrong(Tokenizer):
    def tokenize_words(self, text: str) -> list[tuple[str, int]]:
        return [("a", 2) for char in text if char in ['a', 'A']]

    def tokenize(self, text : str): return []

def test_chunk_paragraph_no_match():
    text = "A"
    paragraphs = _chunk_paragraph(text, max_chunk_size=0, start_pos=0, words=[("a", 1)])
    with pytest.raises(TokenDoesNotExistException):
        list(paragraphs)

def test_chunk_text_no_match():
    text = "A,AA"
    separators = {"," : SepPriority.HIGH}
    tokenizer = TokenizerTestWrong()
    with pytest.raises(TokenDoesNotExistException):
        list(chunk_text(text, separators, tokenizer, 3, force_chunk=True))


class TokenizerTestZero(Tokenizer):
    def tokenize(self, text : str): return []
    def tokenize_words(self, text : str): return [(text, 0)]

def test_chunk_text_zero_token_infinite_loop():
    separators = {
        "\n": SepPriority.HIGH,
        ".": SepPriority.MED,
        ",": SepPriority.LOW,
        " ": SepPriority.LOW
    }
    tokenizer = TokenizerTestZero()
    max_chunk_size = 5

    text = "InvisibleContent" * 5

    chunks = list(chunk_text(text, separators, tokenizer, max_chunk_size, force_chunk=True))

    assert len(chunks) > 0
    assert "".join(c[0] for c in chunks) == text

def test_chunk_text_max_chunk_size():
    separators = separators = {
        "\n": SepPriority.HIGH,
        ".": SepPriority.MED,
        ",": SepPriority.LOW,
        " ": SepPriority.LOW
    }
    tokenizer = TokenizerTestChars()
    max_chunk_size = 10
    text = "a" * 10

    chunks = list(chunk_text(text, separators, tokenizer, max_chunk_size, force_chunk=True))

    assert len(chunks) == 1
    assert len(chunks[0][0]) == 10

def test_chunk_text_unicode():
    separators = separators = {
        "\n": SepPriority.HIGH,
        ".": SepPriority.MED,
        ",": SepPriority.LOW,
        " ": SepPriority.LOW
    }
    tokenizer = TokenizerTestChars()
    text = "😊" * 20
    max_chunk_size = 2

    chunks = list(chunk_text(
        text,
        separators, tokenizer,
        max_chunk_size,
        force_chunk=True
    ))

    reconstructed = "".join(c[0] for c in chunks)
    assert reconstructed == text
