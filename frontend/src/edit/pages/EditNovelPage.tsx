import { extractParams } from "@/routes";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useController } from "../controller/controller";
import { readEditChapterDataEditChapterDataChapterIdGet, type EditChapterData } from "@/client";

function EditNovelPage() {
    const { novelId } = useParams()
    const [searchParams, setSearchParams] = useSearchParams()
    const [chapterId, setChapterId] = useState<string | undefined>(extractParams.edit.novel(searchParams).chapterId);
    const [editChapterData, setEditChapterData] = useState<EditChapterData | null>(null);
    const [error, setError] = useState<unknown>(null);

    useEffect(() => {
        async function navigateToChapter(cid: string | undefined) {
            setChapterId(cid);
        }
        const newChapterId = extractParams.edit.novel(searchParams).chapterId;
        if (newChapterId !== chapterId) {
            void navigateToChapter(newChapterId);
        }
    }, [searchParams]);

    useEffect(() => {
        if (chapterId) {

            readEditChapterDataEditChapterDataChapterIdGet({
                path: {
                    chapterId: chapterId,
                },
                query: {
                    novelId: novelId!,
                    labelGroupsNum: 3,
                }
            }).then((data) => {
                if (data.error) {
                    setError(data.error);
                    setEditChapterData(null);
                }
                else {
                    setEditChapterData(data.data);
                    setError(null);
                }
            }).catch((err) => {
                setError(err);
                setEditChapterData(null);
            });
        }
    }, [chapterId, novelId]);
    

    return <div>EditNovelPage</div>; // temp
}