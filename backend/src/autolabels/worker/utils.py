from collections.abc import Generator

from ..constants import SepPriority
from ..exceptions import ChunkTooLargeException, TokenDoesNotExistException
from .interfaces import Tokenizer


def _chunk_blocks(
    text: str, separators: dict[str, SepPriority]
) -> Generator[tuple[str, int, SepPriority | None], None, None]:
    """
    Separates text into chunks ending with an element in separators. Only supports single character separators. Return format is a generator yielding tuples of (chunk_text, chunk_start_pos, separator_priority).

    Args:
        text: Text to chunk.
        separators: Dictionary of separator characters to split chunks on, along with their priority levels.

    """
    pos_last_sep = 0
    pos = 0
    while pos < len(text):
        if text[pos] in separators:
            yield text[pos_last_sep : pos + 1], pos_last_sep, separators[text[pos]]
            pos_last_sep = pos + 1
        pos += 1
    if pos > pos_last_sep:
        yield text[pos_last_sep:pos], pos_last_sep, None


def _chunk_paragraph(
    text: str, max_chunk_size: int, start_pos: int, words: list[tuple[str, int]]
) -> Generator[tuple[str, int], None, None]:
    """
    Returns a generator that yields chunks of the original text, each chunk having no more than max_chunk_size tokens. Used as a helper function for chunk_text.

    Args:
        text: Text to chunk.
        max_chunk_size: Maximum number of tokens in a chunk.
        start_pos: Starting position in the original text.

    Raises:
        TokenDoesNotExistException: When a word expected in the text is not found.
    """
    chunk_start_offset = 0
    chunk_cur_offset = 0
    chunk_size = 0
    for word, sz in words:
        if chunk_size + sz > max_chunk_size:
            yield text[chunk_start_offset:chunk_cur_offset], start_pos + chunk_start_offset
            chunk_start_offset = chunk_cur_offset
            chunk_size = 0
        chunk_cur_offset = text.find(word, chunk_cur_offset)
        if chunk_cur_offset == -1:
            raise TokenDoesNotExistException
        chunk_cur_offset += len(word)
        chunk_size += sz
    if chunk_size > 0:
        yield text[chunk_start_offset:], start_pos + chunk_start_offset


def chunk_text(
    text: str, separators: dict[str, SepPriority], tokenizer: Tokenizer, max_chunk_size: int, force_chunk: bool = False
) -> Generator[tuple[str, int], None, None]:
    """
    Return a generator that returns chunks of the original text along with their start positions, each chunk having no more than max_chunk_size tokens.

    Args:
        text: Text to chunk.
        separators: A dictionary of separator characters, each associated with some priority. Whenever possible, chunk_text will attempt to make chunks ending with a separator of highest priority.
        max_chunk_size: Maximum number of tokens in a chunk.
        force_chunk: When set to True, may chunk even when a chunk does not end in a separator. When set to False, will throw an error if it is impossible to chunk text in a way that each non-final chunk has a separator at the end.

    Raises:
        ChunkTooLargeException: In the case that force_chunk == False, there is a chunk of text between two separators that has more tokens than max_chunk_size. In the case that force_chunk == True, only raise when there is a word that has more tokens than max_chunk_size.
        TokenDoesNotExistException: Should only happen when force_chunk == True.

    Todo:
        Points of failure to consider:
            - Odd behavior around end of text (no separator at end, massive last chunk)
            - Test invariants more thoroughly
            - Account for odd behavior from tokenizer (e.g. normalization changing length, etc.)
        Test extensively.
    """
    priority_buffers: dict[SepPriority, tuple[int, int, int]] = {
        priority: (0, 0, 0) for priority in SepPriority
    }  # priority : (index in all_buffer, size in tokens of buffer, end pos of buffer)
    all_buffer: list[str] = []  # buffer of lines
    all_buffer_size = 0
    all_buffer_start = 0
    all_buffer_end = 0
    yielded = True
    # Invariant: all_buffer contains only lines ending with separators
    # Invariant: priority_buffers indexes are increasing with respect to priority (e.g. priority_buffers[SepPriority.HIGH][0] <= priority_buffers[SepPriority.MED][0] <= priority_buffers[SepPriority.LOW][0])
    for line, start_pos, priority in _chunk_blocks(text, separators):
        add_to_buffer = True
        words = tokenizer.tokenize_words(line)
        line_size = sum(sz for _, sz in words)
        while all_buffer_size + line_size > max_chunk_size:
            yielded = False
            for prio in SepPriority:
                idx, p_size, p_end = priority_buffers[prio]
                if idx > 0:
                    yield "".join(all_buffer[:idx]), all_buffer_start
                    yielded = True
                    for prio2 in SepPriority:
                        priority_buffers[prio2] = (
                            max(priority_buffers[prio2][0] - idx, 0),
                            max(priority_buffers[prio2][1] - p_size, 0),
                            max(priority_buffers[prio2][2], p_end),
                        )

                    all_buffer = all_buffer[idx:]
                    all_buffer_size = all_buffer_size - p_size
                    all_buffer_start = p_end
                    break
            if not yielded:
                if not force_chunk:
                    raise ChunkTooLargeException
                # try to chunk this line
                yield from _chunk_paragraph(line, max_chunk_size, start_pos, words)
                all_buffer_start = start_pos + len(line)
                all_buffer_end = all_buffer_start
                all_buffer = []
                all_buffer_size = 0
                for prio in SepPriority:
                    priority_buffers[prio] = (0, 0, all_buffer_start)
                add_to_buffer = False
                break
        if not add_to_buffer:
            continue
        all_buffer.append(line)
        all_buffer_size = all_buffer_size + line_size
        all_buffer_end = start_pos + len(line)
        if priority is None:
            # no lines left
            continue
        for prio in SepPriority:
            if prio >= priority:
                priority_buffers[prio] = (len(all_buffer), all_buffer_size, all_buffer_end)
    yield "".join(all_buffer), all_buffer_start
