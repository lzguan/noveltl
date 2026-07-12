import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.auth.models import User
from src.autolabels.constants import AutoLabelProgress, SepPriority
from src.autolabels.models import AutoLabel, AutoLabelRun
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork

from .domain import NovelDataset
from .formats.v1.documents import ModelConfigDocument


@dataclass
class FixtureIdMap:
    novels: dict[str, uuid.UUID] = field(default_factory=dict)
    chapters: dict[str, uuid.UUID] = field(default_factory=dict)
    versions: dict[str, uuid.UUID] = field(default_factory=dict)
    artifacts: dict[str, uuid.UUID] = field(default_factory=dict)


@dataclass
class MaterializedNovel:
    novel: Novel
    chapters: list[tuple[Chapter, ChapterContent]]
    all_contents: dict[str, ChapterContent]
    ids: FixtureIdMap


def make_novel(dataset: NovelDataset, source_work: SourceWork) -> Novel:
    return Novel(
        novel_title=dataset.title,
        novel_description=dataset.description,
        novel_author=dataset.author,
        language_code=dataset.language_code,
        novel_type=NovelType(dataset.novel_type),
        novel_visibility=Visibility[dataset.visibility.upper()],
        source_work_id=source_work.source_work_id,
    )


def materialize_novel_contents(db: Session, dataset: NovelDataset, novel: Novel) -> MaterializedNovel:
    ids = FixtureIdMap(novels={dataset.id: novel.novel_id})
    latest: list[tuple[Chapter, ChapterContent]] = []
    all_contents: dict[str, ChapterContent] = {}
    for chapter_data in dataset.chapters:
        chapter = Chapter(
            chapter_num=chapter_data.number,
            chapter_title=chapter_data.title,
            chapter_is_public=chapter_data.is_public,
            novel_id=novel.novel_id,
        )
        db.add(chapter)
        db.flush()
        ids.chapters[chapter_data.id] = chapter.chapter_id
        latest_content: ChapterContent | None = None
        for version in chapter_data.versions:
            content = ChapterContent(
                chapter_id=chapter.chapter_id,
                chapter_content_text=version.text,
                chapter_content_version=version.number,
            )
            db.add(content)
            db.flush()
            ids.versions[version.id] = content.chapter_content_id
            all_contents[version.id] = content
            if latest_content is None or content.chapter_content_version > latest_content.chapter_content_version:
                latest_content = content
        if latest_content is None:
            raise ValueError(f"Chapter has no content versions: {chapter_data.id}")
        latest.append((chapter, latest_content))
    db.commit()
    return MaterializedNovel(novel=novel, chapters=latest, all_contents=all_contents, ids=ids)


def materialize_latest_autolabels(
    db: Session,
    dataset: NovelDataset,
    materialized: MaterializedNovel,
    config: ModelConfigDocument,
    user: User,
) -> list[AutoLabel]:
    sep_map = {"high": SepPriority.HIGH, "med": SepPriority.MED, "low": SepPriority.LOW}
    separators = {k: sep_map[v] for k, v in config.parameters.separators.items()}
    run = AutoLabelRun(
        novel_id=materialized.novel.novel_id,
        triggered_by=user.user_id,
        model_name=config.model_name,
        model_params={
            "model_name": config.model_name,
            "chunk_size": config.parameters.chunk_size,
            "separators": separators,
            "force_chunk": config.parameters.force_chunk,
        },
    )
    db.add(run)
    db.flush()
    result: list[AutoLabel] = []
    for chapter in dataset.chapters:
        version = max(chapter.versions, key=lambda item: item.number)
        for artifact in version.artifacts:
            if artifact.config_id != config.id:
                continue
            labels = [
                {
                    "label_entity_group": label.entity_group,
                    "label_score": label.score,
                    "label_word": label.text,
                    "label_start": label.start,
                    "label_end": label.end,
                    "label_dirty": False,
                }
                for label in artifact.labels
            ]
            auto_label = AutoLabel(
                auto_label_data=labels,
                auto_label_status=AutoLabelProgress.DONE,
                auto_label_message=None if not artifact.errors else str(artifact.errors),
                auto_label_last_job_id=None,
                chapter_content_id=materialized.all_contents[version.id].chapter_content_id,
                run_id=run.run_id,
            )
            db.add(auto_label)
            db.flush()
            materialized.ids.artifacts[artifact.id] = auto_label.auto_label_id
            result.append(auto_label)
    db.commit()
    return result
