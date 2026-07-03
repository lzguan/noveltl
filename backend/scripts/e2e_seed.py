import json
import os
from pathlib import Path

import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.auth.constants import UserType
from src.auth.models import User
from src.auth.utils import hash_password
from src.labels.constants import LabelRole
from src.labels.models import LabelContributor, LabelData, LabelGroup
from src.languages.models import Language
from src.models import Base
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import (
    Chapter,
    ChapterContent,
    Novel,
    NovelContributor,
    SourceWork,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED_FILE = REPO_ROOT / "e2e" / ".seed.json"


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"{name} must be set for e2e seeding.")
    return value


def reset_redis() -> None:
    host = env("REDIS_HOST", "test_redis")
    port = int(env("REDIS_PORT", "6379"))
    with redis.Redis(host=host, port=port) as client:
        client.flushall()


def main() -> None:
    db_url = env("DB_URL", os.getenv("TEST_URL"))
    seed_file = Path(os.getenv("E2E_SEED_FILE", str(DEFAULT_SEED_FILE)))
    seed_file.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.commit()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session_local = sessionmaker(autoflush=False, bind=engine)
    chapter_text = "Alice went to the market."
    username = "e2e-user"
    password = "e2e-password"

    with session_local() as db:
        en = Language(language_name="English", language_code="en")
        source_work = SourceWork(source_work_title="E2E Source Work")
        user = User(user_name=username, user_hashed_password=hash_password(password), user_type=UserType.ADMIN)
        db.add_all([en, source_work, user])
        db.commit()

        novel = Novel(
            novel_title="E2E Novel",
            novel_description="Seeded novel for Playwright tests.",
            novel_author="E2E Author",
            language_code=en.language_code,
            novel_type=NovelType.ORIGINAL,
            novel_visibility=Visibility.PUBLIC,
            source_work_id=source_work.source_work_id,
        )
        db.add(novel)
        db.commit()

        db.add(NovelContributor(novel_id=novel.novel_id, user_id=user.user_id, contributor_role=Role.OWNER))
        chapter = Chapter(
            novel_id=novel.novel_id,
            chapter_num=1,
            chapter_title="The Beginning",
            chapter_is_public=True,
        )
        db.add(chapter)
        db.commit()

        content = ChapterContent(
            chapter_id=chapter.chapter_id,
            chapter_content_text=chapter_text,
            chapter_content_version=1,
        )
        db.add(content)
        db.commit()

        label_group = LabelGroup(label_group_name="E2E Labels", novel_id=novel.novel_id)
        db.add(label_group)
        db.commit()

        db.add_all(
            [
                LabelContributor(
                    label_group_id=label_group.label_group_id,
                    user_id=user.user_id,
                    label_contributor_role=LabelRole.OWNER,
                ),
                LabelData(
                    label_group_id=label_group.label_group_id,
                    chapter_content_id=content.chapter_content_id,
                ),
            ]
        )
        db.commit()
        db.refresh(novel)
        db.refresh(chapter)
        db.refresh(content)

        seed = {
            "user": {"username": username, "password": password},
            "novelId": str(novel.novel_id),
            "chapterId": str(chapter.chapter_id),
            "chapterTitle": chapter.chapter_title,
            "chapterText": chapter_text,
            "chapterContentId": str(content.chapter_content_id),
            "chapterContentVersion": content.chapter_content_version,
            "labelGroupId": str(label_group.label_group_id),
        }

    seed_file.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
    reset_redis()
    engine.dispose()


if __name__ == "__main__":
    main()
