"""
This module provides global db models.
"""
from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped
from sqlalchemy.orm import mapped_column

class Base(DeclarativeBase):
    """
    Class for base model.

    Attributes:
        created_at: Date and time object was created in db.
        updated_at: Date and time object was last updated in db.
    """
    created_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.now(), nullable=False)
    updated_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.now(), onupdate=datetime.now(), nullable=False)


# imports for other models
from .languages.models import *
from .auth.models import *
from .novels.models import *
from .translations.models import *
from .labels.models import *