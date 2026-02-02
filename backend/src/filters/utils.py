import logging

logger = logging.getLogger(__name__)

def find_sentence_around(text: str, label_start: int, label_end: int, delimiters: str) -> tuple[str, int, int]:
    """
    Finds the sentence surrounding a labeled segment in the text. Returns in the format (sentence, label_start, label_end).
    """
    # Find sentence start (last delimiter before label_start)
    start = 0
    for delim in delimiters:
        pos = text.rfind(delim, 0, label_start)
        if pos != -1 and pos + 1 > start:
            start = pos + 1

    # Find sentence end (first delimiter after label_end)
    end = len(text)
    for delim in delimiters:
        pos = text.find(delim, label_end)
        if pos != -1 and pos + 1 < end:
            end = pos + 1

    if end - start > 500:
        logger.warning(
            "find_sentence_around returned %d chars (label: %d-%d). Possibly missing delimiter.",
            end - start, label_start, label_end
        )

    return text[start:end].strip(), label_start - start, label_end - start
