"""
This module provides global db models.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """
    Class for base model.

    Attributes:
        created_at: Date and time object was created in db.
        updated_at: Date and time object was last updated in db.
    """

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


# imports for other models
from .auth.models import *  # noqa: E402, F403
from .autolabels.models import *  # noqa: E402, F403
from .glossaries.models import *  # noqa: E402, F403
from .labels.models import *  # noqa: E402, F403
from .languages.models import *  # noqa: E402, F403
from .novels.models import *  # noqa: E402, F403
