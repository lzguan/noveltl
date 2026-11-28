# Generated from reader-api/openapi.json (/ingest/*) by backend/scripts/generate_reader_schemas.py. Do not edit manually.

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints


class IngestChapterStatus(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    chapter_num: Annotated[int, Field(alias="chapterNum", title="Chapternum")]
    title: Annotated[str, Field(title="Title")]
    content_hash: Annotated[str, Field(alias="contentHash", title="Contenthash")]
    external_version: Annotated[str | None, Field(alias="externalVersion", title="Externalversion")]
    updated_at: Annotated[AwareDatetime, Field(alias="updatedAt", title="Updatedat")]


class IngestChapterUpsertItem(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    chapter_num: Annotated[int, Field(alias="chapterNum", ge=0, title="Chapternum")]
    title: Annotated[str, Field(max_length=512, title="Title")]
    body: Annotated[str, Field(title="Body")]
    external_version: Annotated[
        Annotated[str, StringConstraints(max_length=128)] | None,
        Field(alias="externalVersion", title="Externalversion"),
    ] = None


class IngestHealthResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    ok: Annotated[bool, Field(title="Ok")] = True
    protocol_version: Annotated[int, Field(alias="protocolVersion", title="Protocolversion")] = 1
    name: Annotated[str, Field(title="Name")]
    public_base_url: Annotated[str, Field(alias="publicBaseUrl", title="Publicbaseurl")]


class IngestNovelStatusResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    exists: Annotated[bool, Field(title="Exists")]
    novel_id: Annotated[UUID | None, Field(alias="novelId", title="Novelid")] = None
    public_url: Annotated[str | None, Field(alias="publicUrl", title="Publicurl")] = None
    chapters: Annotated[list[IngestChapterStatus] | None, Field(title="Chapters")] = None


class IngestNovelSyncResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    novel_id: Annotated[UUID, Field(alias="novelId", title="Novelid")]
    public_url: Annotated[str, Field(alias="publicUrl", title="Publicurl")]
    upserted_chapter_nums: Annotated[list[int], Field(alias="upsertedChapterNums", title="Upsertedchapternums")]


class IngestNovelUpsertRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    title: Annotated[str, Field(max_length=512, min_length=1, title="Title")]
    description: Annotated[str | None, Field(title="Description")] = None
    author: Annotated[Annotated[str, StringConstraints(max_length=255)] | None, Field(title="Author")] = None
    language_code: Annotated[str, Field(alias="languageCode", max_length=32, min_length=1, title="Languagecode")] = "en"


class IngestNovelSyncRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    novel: IngestNovelUpsertRequest | None = None
    upserts: Annotated[list[IngestChapterUpsertItem] | None, Field(max_length=200, title="Upserts")] = None
