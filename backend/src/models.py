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

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


# Import model modules for side effects so SQLAlchemy registers every table.
from .auth import models as _auth_models  # noqa: E402, F401
from .autolabels import models as _autolabel_models  # noqa: E402, F401
from .labels import models as _label_models  # noqa: E402, F401
from .languages import models as _language_models  # noqa: E402, F401
from .novels import models as _novel_models  # noqa: E402, F401
