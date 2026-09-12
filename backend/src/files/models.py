import uuid

from sqlalchemy import BigInteger, CheckConstraint, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UUID

from src.models import Base


class StoredFile(Base):
    """Metadata for one immutable object stored outside PostgreSQL."""

    __tablename__ = "stored_files"

    file_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    storage_name: Mapped[str] = mapped_column(String(32), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    content_encoding: Mapped[str | None] = mapped_column(String(64), nullable=True)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    etag: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("storage_name", "bucket", "object_key", name="uq_stored_files_location"),
        CheckConstraint("byte_size >= 0", name="ck_stored_files_byte_size"),
    )
