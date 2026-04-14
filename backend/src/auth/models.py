"""
Database models related to users/user authentication
"""
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import Base
from .constants import MAX_USER_NAME_LEN, UserType

if TYPE_CHECKING:
    from ..labels.models import LabelContributor
    from ..novels.models import NovelContributor

class User(Base):
    """
    Database model for User.

    Attributes:
        user_id: Integer identifier for a user.
        user_name: String name for a user. Must be unique, cannot be null. Max length is MAX_USER_NAME_LEN.
        user_hashed_password: Hashed value of a user's password. Cannot be null. Has length up to 256 chars.
        user_type: A UserType (e.g. 'admin', 'user', etc.). Possible values can be found in ./constants.py.
    """
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid())
    user_name : Mapped[str] = mapped_column(
        String(MAX_USER_NAME_LEN),
        nullable=False
    )
    user_hashed_password : Mapped[str] = mapped_column(
        String(256),
        nullable=False
    )
    user_type : Mapped[UserType] = mapped_column(
        Enum(UserType, native_enum=False, length=10, values_callable=lambda x : [str(e.value) for e in x]), # type: ignore
        nullable=False
    )

    novel_contributors_with_user : Mapped[list["NovelContributor"]] = relationship(back_populates='user_of_novel_contributor')
    label_contributors_with_user : Mapped[list["LabelContributor"]] = relationship(back_populates='user_of_label_contributor')

    __table_args__ = (
        UniqueConstraint('user_name', name='uq_user_name'),
    )
