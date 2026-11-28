import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx2


@dataclass
class RecordingPublishDispatcher:
    jobs: list[uuid.UUID] = field(default_factory=list)
    enqueue_error: Exception | None = None

    async def aenqueue(self, job_id: uuid.UUID) -> None:
        if self.enqueue_error is not None:
            raise self.enqueue_error
        self.jobs.append(job_id)


@dataclass
class FakeReaderNovel:
    novel_id: uuid.UUID
    external_id: str
    title: str
    description: str | None
    author: str | None
    language_code: str
    chapters: dict[int, dict[str, Any]] = field(default_factory=dict)


class FakeReaderServer:
    def __init__(
        self,
        *,
        valid_api_keys: set[str] | None = None,
        instance_name: str = "Test Reader",
        public_base_url: str = "https://reader.example.com",
        protocol_version: int = 1,
        ok: bool = True,
    ) -> None:
        self.valid_api_keys: set[str] = set(valid_api_keys or {"rapi_test_secret_key_1234567890"})
        self.instance_name = instance_name
        self.public_base_url = public_base_url
        self.protocol_version = protocol_version
        self.ok = ok
        self.novels: dict[str, FakeReaderNovel] = {}
        self.requests: list[tuple[str, str, dict[str, Any] | None]] = []
        self.fail_on_sync_call: int | None = None
        self.sync_call_count = 0

    def seed_novel(
        self,
        external_id: str,
        *,
        title: str = "Seeded Novel",
        chapters: dict[int, tuple[str, str, str | None]] | None = None,
    ) -> FakeReaderNovel:
        novel_id = uuid.uuid4()
        chapter_map: dict[int, dict[str, Any]] = {}
        for num, (ch_title, body, ext_ver) in (chapters or {}).items():
            chapter_map[num] = {
                "chapterNum": num,
                "title": ch_title,
                "body": body,
                "contentHash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "externalVersion": ext_ver,
                "updatedAt": datetime.now(UTC).isoformat(),
            }
        novel = FakeReaderNovel(
            novel_id=novel_id,
            external_id=external_id,
            title=title,
            description=None,
            author=None,
            language_code="en",
            chapters=chapter_map,
        )
        self.novels[external_id] = novel
        return novel

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self._handle)

    def _public_url(self, novel_id: uuid.UUID) -> str:
        return f"{self.public_base_url.rstrip('/')}/novels/{novel_id}"

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        body: dict[str, Any] | None = None
        if request.content:
            body = json.loads(request.content)
        self.requests.append((request.method, request.url.path, body))

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth.removeprefix("Bearer ") not in self.valid_api_keys:
            return httpx2.Response(401, json={"detail": "Invalid or revoked API key"})

        path = request.url.path
        if request.method == "GET" and path.endswith("/ingest/health"):
            return httpx2.Response(
                200,
                json={
                    "ok": self.ok,
                    "protocolVersion": self.protocol_version,
                    "name": self.instance_name,
                    "publicBaseUrl": self.public_base_url,
                },
            )

        if request.method == "GET" and "/ingest/novels/" in path and path.endswith("/status"):
            external_id = path.split("/ingest/novels/", 1)[1].removesuffix("/status")
            novel = self.novels.get(external_id)
            if novel is None:
                return httpx2.Response(
                    200,
                    json={"exists": False, "novelId": None, "publicUrl": None, "chapters": []},
                )
            chapters = [
                {
                    "chapterNum": ch["chapterNum"],
                    "title": ch["title"],
                    "contentHash": ch["contentHash"],
                    "externalVersion": ch["externalVersion"],
                    "updatedAt": ch["updatedAt"],
                }
                for _, ch in sorted(novel.chapters.items())
            ]
            return httpx2.Response(
                200,
                json={
                    "exists": True,
                    "novelId": str(novel.novel_id),
                    "publicUrl": self._public_url(novel.novel_id),
                    "chapters": chapters,
                },
            )

        if request.method == "POST" and "/ingest/novels/" in path and path.endswith("/sync"):
            self.sync_call_count += 1
            if self.fail_on_sync_call is not None and self.sync_call_count == self.fail_on_sync_call:
                return httpx2.Response(500, json={"detail": "Simulated reader failure"})

            external_id = path.split("/ingest/novels/", 1)[1].removesuffix("/sync")
            payload = body or {}
            novel_meta = payload.get("novel")
            upserts = payload.get("upserts") or []

            novel = self.novels.get(external_id)
            if novel_meta is not None:
                if novel is None:
                    novel = FakeReaderNovel(
                        novel_id=uuid.uuid4(),
                        external_id=external_id,
                        title=novel_meta["title"],
                        description=novel_meta.get("description"),
                        author=novel_meta.get("author"),
                        language_code=novel_meta.get("languageCode", "en"),
                    )
                    self.novels[external_id] = novel
                else:
                    novel.title = novel_meta["title"]
                    novel.description = novel_meta.get("description")
                    novel.author = novel_meta.get("author")
                    novel.language_code = novel_meta.get("languageCode", "en")
            elif novel is None:
                return httpx2.Response(
                    404,
                    json={"detail": "Novel not found; include novel metadata to create it"},
                )

            upserted_nums: list[int] = []
            for item in upserts:
                ch_num = int(item["chapterNum"])
                novel.chapters[ch_num] = {
                    "chapterNum": ch_num,
                    "title": item["title"],
                    "body": item["body"],
                    "contentHash": hashlib.sha256(item["body"].encode("utf-8")).hexdigest(),
                    "externalVersion": item.get("externalVersion"),
                    "updatedAt": datetime.now(UTC).isoformat(),
                }
                upserted_nums.append(ch_num)

            return httpx2.Response(
                200,
                json={
                    "novelId": str(novel.novel_id),
                    "publicUrl": self._public_url(novel.novel_id),
                    "upsertedChapterNums": sorted(set(upserted_nums)),
                },
            )

        return httpx2.Response(404, json={"detail": f"Unhandled route: {request.method} {path}"})
