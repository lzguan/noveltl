import { makeBasicSegmentManager } from "@/components/labeled-text-lib/core/segmentManager";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import type { ColorStyle } from "@/components/labeled-text-lib/builtin/reducers";
import { makePlainBoxRenderer } from "@/components/labeled-text-lib/react/Renderer";
import { toHex } from "@/components/labeled-text-lib/builtin/colors";
import { useParams, useSearchParams } from "react-router-dom";
import { extractParams } from "@/routes";
import { useLoader } from "@/lib/utils";
import { readEditChapterDataEditChapterDataChapterIdGet } from "@/client";

export function EditNovelPage({ loadLabelsNum = 3 } : { loadLabelsNum: number }) {
    const renderer = makePlainBoxRenderer<ColorStyle, StyledLabel<ColorStyle>>((style) => ({
        backgroundColor: toHex(style.color),
        display: "inline-block",
        width: "100%",
        height: "100%",
    }));

    const [searchParams, setSearchParams] = useSearchParams();
    const chapterId = useMemo(() => {
        return extractParams.edit.novel(searchParams).chapterId;
    }, [searchParams]);
    const params = useParams<"novelId">();

    const loadNovel = () => {
        if (!params.novelId) {
            return Promise.reject(new Error("No novel ID provided in URL"));
        }
        return getNovelById(params.novelId);
    };

    const [novel, novelLoading, novelError, reloadNovel] = useLoader<Novel | null>(
        null,
        loadNovel,
        [params.novelId],
    );

    const loadChapterList = () => {
        if (!params.novelId) {
            return Promise.reject(new Error("No novel ID provided in URL"));
        }
        return getChaptersByNovel(params.novelId);
    };

    const [chapterList, chapterListLoading, chapterListError, reloadChapterList] = useLoader<Chapter[]>([], loadChapterList, [params.novelId]);

    const loadEditChapterData = () => {
        if (!chapterId || !params.novelId) {
            return Promise.reject(new Error("No chapter ID or novel ID provided in URL"));
        }

        return readEditChapterDataEditChapterDataChapterIdGet(chapterId, {
            novelId: params.novelId,
            labelGroupsNum: loadLabelsNum,
        });
    };

    const [editChapterData, editChapterDataLoading, editChapterDataError, reloadEditChapterData] = useLoader<EditChapterData | null>(null, loadEditChapterData, [params.novelId, chapterId]);
}
