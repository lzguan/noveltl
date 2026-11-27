import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class HealthzResponse(Model):
    ok: bool = True


class IngestHealthResponse(Model):
    ok: bool = True
    protocol_version: int = 1
    name: str
    public_base_url: str


class IngestChapterStatus(Model):
    chapter_num: int
    title: str
    content_hash: str
    external_version: str | None
    updated_at: datetime


class IngestNovelStatusResponse(Model):
    exists: bool
    novel_id: uuid.UUID | None = None
    public_url: str | None = None
    chapters: list[IngestChapterStatus] = Field(default_factory=list)


class IngestNovelUpsertRequest(Model):
    title: str = Field(min_length=1, max_length=512)
    description: str | None = None
    author: str | None = Field(default=None, max_length=255)
    language_code: str = Field(default="en", min_length=1, max_length=32)


class IngestChapterUpsertItem(Model):
    chapter_num: int = Field(ge=0)
    title: str = Field(max_length=512)
    body: str
    external_version: str | None = Field(default=None, max_length=128)


class IngestNovelSyncRequest(Model):
    novel: IngestNovelUpsertRequest | None = None
    upserts: list[IngestChapterUpsertItem] = Field(default_factory=list, max_length=200)


class IngestNovelSyncResponse(Model):
    novel_id: uuid.UUID
    public_url: str
    upserted_chapter_nums: list[int]


class AdminLoginRequest(Model):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


class AdminLoginResponse(Model):
    access_token: str
    expires_at: datetime


class AdminPartnerKeySummary(Model):
    key_id: uuid.UUID
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None


class AdminPartnerSummary(Model):
    partner_id: uuid.UUID
    name: str
    created_at: datetime
    novel_count: int
    keys: list[AdminPartnerKeySummary]


class AdminPartnerCreateRequest(Model):
    name: str = Field(min_length=1, max_length=255)


class AdminPartnerCreateResponse(Model):
    partner_id: uuid.UUID
    name: str
    created_at: datetime


class AdminMintKeyResponse(Model):
    key_id: uuid.UUID
    key_prefix: str
    api_key: str
    created_at: datetime


class AdminNovelSummary(Model):
    novel_id: uuid.UUID
    title: str
    author: str | None
    language_code: str
    partner_id: uuid.UUID | None
    partner_name: str | None
    chapter_count: int
    updated_at: datetime
    public_url: str


class PublicNovelSummary(Model):
    novel_id: uuid.UUID
    title: str
    description: str | None
    author: str | None
    language_code: str
    updated_at: datetime


class PublicChapterSummary(Model):
    chapter_id: uuid.UUID
    chapter_num: int
    title: str
    published_at: datetime
    updated_at: datetime


class PublicChapterNav(Model):
    chapter_num: int
    title: str


class PublicChapterDetail(Model):
    novel_id: uuid.UUID
    novel_title: str
    chapter_id: uuid.UUID
    chapter_num: int
    title: str
    body: str
    content_hash: str
    external_version: str | None
    prev: PublicChapterNav | None
    next: PublicChapterNav | None
