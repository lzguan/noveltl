import uuid

import pytest
from sqlalchemy.orm import Session

from src.filters.context.python import PythonExecutionContextImpl


def test_preload_rejects_missing_chapter_content(test_db: Session) -> None:
    missing_id = uuid.uuid4()

    with pytest.raises(ValueError, match=str(missing_id)):
        PythonExecutionContextImpl(test_db).load_resources(
            {"chapter_content_text": {missing_id}}
        )
