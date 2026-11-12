from dataclasses import dataclass, replace
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.models import MemoryChapterTask, MemoryGroup, MemoryJob
from src.memory.shadow_models import MemoryWorkspace
from src.novels.models import ChapterContent
from test_support.test_data.scenarios import DatabaseScenario


@dataclass
class ReadScenario:
    published: MemAccessContext
    current: MemAccessContext
    other: MemAccessContext
    predecessor: MemAccessContext

    @property
    def workspace_id(self) -> UUID:
        assert self.current.workspace_id is not None
        return self.current.workspace_id


@pytest.fixture
def reads(test_db: Session, sample_scenario: DatabaseScenario) -> ReadScenario:
    source = sample_scenario.contents["chapter_1_v2"]
    source.chapter_content_text = "Alpha Beta Gamma Delta Epsilon"
    chapter = sample_scenario.chapters["chapter_2"]
    content = ChapterContent(
        chapter_id=chapter.chapter_id,
        chapter_content_version=1,
        chapter_content_text="Alpha Beta Gamma Delta Epsilon Zeta",
    )
    group = MemoryGroup(novel_id=chapter.novel_id, memory_group_name="Shadow reads", memory_language="en")
    test_db.add_all([content, group])
    test_db.flush()
    job = MemoryJob(memory_group_id=group.memory_group_id, job_params={})
    test_db.add(job)
    test_db.flush()
    test_db.add(MemoryChapterTask(memory_job_id=job.memory_job_id, chapter_id=chapter.chapter_id, stage_num=0))
    test_db.flush()
    workspaces = [
        MemoryWorkspace(memory_job_id=job.memory_job_id, chapter_id=chapter.chapter_id, stage_num=0) for _ in range(2)
    ]
    test_db.add_all(workspaces)
    test_db.flush()
    published = MemAccessContext(group.memory_group_id, chapter.chapter_id, content.chapter_content_id)
    return ReadScenario(
        published,
        replace(published, workspace_id=workspaces[0].workspace_id),
        replace(published, workspace_id=workspaces[1].workspace_id),
        MemAccessContext(group.memory_group_id, source.chapter_id, source.chapter_content_id),
    )
