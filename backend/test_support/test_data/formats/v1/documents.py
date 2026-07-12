from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Document(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    schema_uri: str = Field(alias="$schema")
    schema_version: Literal[1]


class Reference(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1)
    path: str = Field(min_length=1)


class CatalogDocument(Document):
    kind: Literal["testDataCatalog"]
    configs: list[Reference]
    novels: list[Reference]
    relations: list[Reference]


class CluenerParameters(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    chunk_size: int = Field(ge=1, le=512)
    force_chunk: bool
    separators: dict[str, Literal["high", "med", "low"]]


class ModelConfigDocument(Document):
    kind: Literal["modelConfig"]
    id: str = Field(min_length=1)
    config_type: Literal["ner"]
    model_name: Literal["cluener"]
    parameters: CluenerParameters


class Provenance(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    kind: str = Field(min_length=1)
    creator: str = Field(min_length=1)
    license: str = Field(min_length=1)


class ChapterReference(Reference):
    number: int


class NovelManifestDocument(Document):
    kind: Literal["novelManifest"]
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None
    author: str | None
    language_code: str = Field(min_length=1)
    novel_type: Literal["original", "translation", "other"]
    visibility: Literal["private", "restricted", "unlisted", "public"]
    provenance: Provenance
    chapters: list[ChapterReference]


class ChapterManifestDocument(Document):
    kind: Literal["chapterManifest"]
    id: str = Field(min_length=1)
    number: int
    title: str
    is_public: bool
    versions: list[Reference] = Field(min_length=1)


class ArtifactReference(Reference):
    kind: str = Field(min_length=1)


class ContentVersionManifestDocument(Document):
    kind: Literal["contentVersionManifest"]
    id: str = Field(min_length=1)
    number: int = Field(ge=1)
    text: str = Field(min_length=1)
    artifacts: list[ArtifactReference]


class Producer(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    name: str = Field(min_length=1)
    config: str = Field(min_length=1)


class AutoLabel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(ge=1)
    text: str = Field(min_length=1)
    entity_group: str | None
    score: float = Field(ge=0, le=1)


class AutoLabelsDocument(Document):
    kind: Literal["autolabels"]
    id: str = Field(min_length=1)
    producer: Producer
    labels: list[AutoLabel]
    errors: list[dict[str, Any]]


class SourceWorkDocument(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None
    novels: list[str] = Field(min_length=1)


class RelationBundleDocument(Document):
    kind: Literal["relationBundle"]
    id: str = Field(min_length=1)
    source_works: list[SourceWorkDocument]


class LockInputs(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    text_sha256: str | None = None
    config_sha256: str | None = None


class LockFileEntry(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    kind: str
    size: int = Field(ge=0)
    sha256: str
    inputs: LockInputs | None = None


class CatalogLockDocument(Document):
    kind: Literal["testDataLock"]
    dataset_schema_version: Literal[1]
    files: dict[str, LockFileEntry]


DocumentType = Annotated[
    CatalogDocument
    | ModelConfigDocument
    | NovelManifestDocument
    | ChapterManifestDocument
    | ContentVersionManifestDocument
    | AutoLabelsDocument
    | RelationBundleDocument
    | CatalogLockDocument,
    Field(discriminator="kind"),
]

DOCUMENT_MODELS: dict[tuple[str, int], type[Document]] = {
    ("testDataCatalog", 1): CatalogDocument,
    ("modelConfig", 1): ModelConfigDocument,
    ("novelManifest", 1): NovelManifestDocument,
    ("chapterManifest", 1): ChapterManifestDocument,
    ("contentVersionManifest", 1): ContentVersionManifestDocument,
    ("autolabels", 1): AutoLabelsDocument,
    ("relationBundle", 1): RelationBundleDocument,
    ("testDataLock", 1): CatalogLockDocument,
}

SCHEMA_MODELS: dict[str, type[Document]] = {
    "test-data-catalog.schema.json": CatalogDocument,
    "model-config.schema.json": ModelConfigDocument,
    "novel-manifest.schema.json": NovelManifestDocument,
    "chapter-manifest.schema.json": ChapterManifestDocument,
    "content-version-manifest.schema.json": ContentVersionManifestDocument,
    "autolabels.schema.json": AutoLabelsDocument,
    "relation-bundle.schema.json": RelationBundleDocument,
    "catalog-lock.schema.json": CatalogLockDocument,
}
