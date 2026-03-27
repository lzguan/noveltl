import logging
from typing import Any, Protocol, TypeVar

from ...labels.schemas import LabelBase
from .. import schemas

my_logger = logging.getLogger(__name__)
my_logger.propagate = True

class Tokenizer(Protocol):
    """
    Abstract class for a tokenizer for use in NER models.
    """
    def tokenize(self, text : str) -> list[str]:
        """
        Returns a list of token strings.

        Args:
            text: Text to tokenize.
        """
        ...

    def tokenize_words(self, text : str) -> list[tuple[str, int]]:
        """
        Returns a list of tuples (word, num_tokens).

        Args:
            text: Text to tokenize.
        """
        ...

P = TypeVar('P', contravariant=True, bound=schemas.NERModelParamsBase)
class NERModel(Protocol[P]):
    """
    Abstract class for a NER model.

    Attributes:
        model_name: Name of the NER model.
        is_deterministic: Whether the model is deterministic.
    """

    model_name : str
    is_deterministic : bool

    def predict(self, text : str, params : P) -> tuple[list[LabelBase], Any]:
        """
        Returns a list of named entities in text in the format
            ```
            {
                'entity_group' : ...
                'score' : ...
                'word' : ...
                'start' : ...
                'end' : ...
            }
            ```
        Acts as a wrapper for calling model_predict.

        Args:
            text: Text to predict on.
            params: Parameters for the NER model.
        """
        ...

    def get_tokenizer(self) -> Tokenizer:
        """
        Returns the tokenizer used by this NER model.
        """
        ...

    def normalize(self, text : str) -> str:
        """
        Normalizes text to match the format of the model's output labels.
        e.g. "Red" -> "red" for case-insensitive models.

        Args:
            text: Text to normalize.
        """
        ...

    def validate(self, params : dict[str, str | int | float | bool]) -> schemas.NERModelParamsBase:
        """
        Validates an arbitrary dictionary of parameters. Raises an error if validation fails.

        Args:
            params: Dictionary to validate.

        Raises:
            ValidationError: If validation fails.
        """
        ...
