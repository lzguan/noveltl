import { extractParams } from "@/routes";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { buildController } from "../controller/controller";
import { buildRuntime } from "../controller/utils";
import {
  readChapterByIdChaptersChapterIdGet,
  readEditChapterDataEditChapterDataChapterIdGet,
  readNovelNovelsNovelIdGet,
  type Chapter,
  type EditChapterData,
  type Novel,
} from "@/client";
import type { Controller, LabelGroupView, EditorMode, Runtime } from "../controller/types";

function EditNovelPage({ userId }: { userId: string }) {
  const { novelId } = useParams();
  const [novel, setNovel] = useState<Novel | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [chapterId, setChapterId] = useState<string | undefined>(
    extractParams.edit.novel(searchParams).chapterId,
  );
  const [chapter, setChapter] = useState<null | Chapter>(null);
  const [editChapterData, setEditChapterData] = useState<EditChapterData | null>(null);
  const [error, setError] = useState<unknown>(null);

  const [controller, setController] = useState<null | Controller>(null);

  const [labelGroupViews, setLabelGroupViews] = useState<LabelGroupView[]>([]);
  const [activeLabelGroupId, setActiveLabelGroupId] = useState<string | null>(null);
  const [mode, setMode] = useState<EditorMode>("view");

  useEffect(() => {
    async function navigateToChapter(cid: string | undefined) {
      setChapterId(cid);
    }
    const newChapterId = extractParams.edit.novel(searchParams).chapterId;
    if (newChapterId !== chapterId) {
      void navigateToChapter(newChapterId);
    }
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  useEffect(() => {
    if (!novelId) {
      setNovel(null);
      setError(new Error("Novel ID is required"));
      return;
    }
    if (chapterId) {
      readNovelNovelsNovelIdGet({
        path: {
          novelId: novelId,
        },
      })
        .then((data) => {
          if (data.error) {
            throw data.error;
          } else {
            setNovel(data.data);
            setError(null);
          }
        })
        .catch((err) => {
          setError(err);
          setNovel(null);
        })
        .then(() => {
          return readChapterByIdChaptersChapterIdGet({
            path: {
              chapterId: chapterId,
            },
          });
        })
        .catch((err) => {
          setError(err);
          setChapter(null);
        })
        .then((data) => {
          if (!data) {
            throw new Error("Unknown error");
          } else if (data.error) {
            throw data.error;
          } else {
            setError(null);
            setChapter(data.data);
          }
        })
        .catch((err) => {
          setError(err);
          setChapter(null);
        })
        .then(() => {
          return readEditChapterDataEditChapterDataChapterIdGet({
            path: {
              chapterId: chapterId,
            },
            query: {
              novelId: novelId!,
              labelGroupsNum: 3,
            },
          }).then((data) => {
            if (data.error) {
              throw data.error;
            }
            return data.data;
          });
        })
        .catch((err) => {
          setError(err);
          setEditChapterData(null);
        })
        .then((data) => {
          if (!data) {
            throw new Error("Unknown error");
          }
          setEditChapterData(data);
          setError(null);
        })
        .then(() => {
          const rt = buildRuntime(setError, novel!, chapter!, editChapterData!, userId);
          const ctrl = buildController(
            editChapterData!,
            () => mode,
            setMode,
            rt,
            setError,
            setLabelGroupViews,
            setActiveLabelGroupId,
          );
          setController(ctrl);
        });
    } else {
      setChapter(null);
    }
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterId, novelId]);

  return <div>EditNovelPage</div>; // temp
}

export { EditNovelPage };
