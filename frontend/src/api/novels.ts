import client from './client'
import * as NovelType from '../types/novel'

/* eslint-disable @typescript-eslint/no-explicit-any */

const mapSourceWork = (data: any): NovelType.SourceWork => ({
    sourceWorkId: data.source_work_id,
    sourceWorkTitle: data.source_work_title,
    sourceWorkDescription: data.source_work_description,
})

const mapNovel = (data: any): NovelType.Novel => ({
    novelId: data.novel_id,
    novelTitle: data.novel_title,
    novelDescription: data.novel_description,
    novelAuthor: data.novel_author,
    novelVisibility: data.novel_visibility,
    novelType: data.novel_type,
    languageCode: data.language_code,
})

const mapChapter = (data: any): NovelType.Chapter => ({
    chapterId: data.chapter_id,
    chapterNum: data.chapter_num,
    chapterTitle: data.chapter_title,
    chapterIsPublic: data.chapter_is_public,
    novelId: data.novel_id,
})

const mapChapterContent = (data: any): NovelType.ChapterContent => ({
    chapterContentText: data.chapter_content_text,
    chapterContentVersion: data.chapter_content_version,
    chapterContentId: data.chapter_content_id,
})

const mapChapterContentMeta = (data: any): NovelType.ChapterContentMeta => ({
    chapterContentVersion: data.chapter_content_version,
    chapterContentId: data.chapter_content_id,
})

const mapChapterData = (data: any): NovelType.ChapterData => ({
    metadata: mapChapter(data.metadata),
    content: mapChapterContent(data.content),
})

const mapOperationStatus = (data: any): NovelType.OperationStatus => ({
    status: data.status,
    detail: data.detail,
})

const mapCreateSourceWorkRequest = (data: NovelType.CreateSourceWork) => ({
    source_work_title: data.sourceWorkTitle,
    source_work_description: data.sourceWorkDescription,
})

const mapUpdateSourceWorkRequest = (data: NovelType.UpdateSourceWork) => ({
    source_work_title: data.sourceWorkTitle,
    source_work_description: data.sourceWorkDescription,
})

const mapCreateNovelRequest = (data: NovelType.CreateNovel) => ({
    novel_title: data.novelTitle,
    novel_description: data.novelDescription,
    novel_author: data.novelAuthor,
    novel_visibility: data.novelVisibility,
    novel_type: data.novelType,
    language_code: data.languageCode,
    source_work_id: data.sourceWorkId,
})

const mapUpdateNovelRequest = (data: NovelType.UpdateNovel) => ({
    novel_title: data.novelTitle,
    novel_description: data.novelDescription,
    novel_author: data.novelAuthor,
    novel_visibility: data.novelVisibility,
    novel_type: data.novelType,
})

const mapCreateChapterRequest = (data: NovelType.CreateChapter) => ({
    chapter_num: data.chapterNum,
    chapter_title: data.chapterTitle,
    chapter_is_public: data.chapterIsPublic,
})

const mapUpdateChapterRequest = (data: NovelType.UpdateChapter) => ({
    chapter_title: data.chapterTitle,
})

const mapUpdateChapterContentRequest = (data: NovelType.UpdateChapterContent) => ({
    text_ops: data.textOps.map(op => ({
        op: op.op,
        start: op.start,
        text: op.text,
    })),
    chapter_content_id: data.chapterContentId,
})

/* eslint-enable @typescript-eslint/no-explicit-any */

export const getSourceWorks = async (titleContains? : string) : Promise<NovelType.SourceWork[]> => {
    const result = await client.get('/source-works', {
        params: {
            'title-contains': titleContains
        }
    })
    return result.data.map(mapSourceWork)
}

export const getSourceWorkById = async (sourceWorkId : string) : Promise<NovelType.SourceWork> => {
    const result = await client.get(`/source-works/${sourceWorkId}`)
    return mapSourceWork(result.data)
}

export const getNovelsBySourceWork = async (sourceWorkId : string) : Promise<NovelType.Novel[]> => {
    const result = await client.get(`/source-works/${sourceWorkId}/novels`)
    return result.data.map(mapNovel)
}

export const createSourceWork = async (request : NovelType.CreateSourceWork) : Promise<NovelType.SourceWork> => {
    const result = await client.post('/source-works', mapCreateSourceWorkRequest(request))
    return mapSourceWork(result.data)
}

export const updateSourceWork = async (
    sourceWorkId : string,
    request : NovelType.UpdateSourceWork
) : Promise<NovelType.SourceWork> => {
    const result = await client.patch(`/source-works/${sourceWorkId}`, mapUpdateSourceWorkRequest(request))
    return mapSourceWork(result.data)
}

export const getNovels = async (titleContains? : string) : Promise<NovelType.Novel[]> => {
    const result = await client.get('/novels', {
        params: {
            'title-contains': titleContains
        }
    })
    return result.data.map(mapNovel)
}

export const getNovelsMine = async (editable : boolean, titleContains? : string) : Promise<NovelType.Novel[]> => {
    const result = await client.get('/novels/mine', {
        params: {
            editable,
            'title-contains': titleContains
        }
    })
    return result.data.map(mapNovel)
}

export const getNovelById = async (novelId : string) : Promise<NovelType.Novel> => {
    const result = await client.get(`/novels/${novelId}`)
    return mapNovel(result.data)
}

export const createNovel = async (request : NovelType.CreateNovel) : Promise<NovelType.Novel> => {
    const result = await client.post('/novels', mapCreateNovelRequest(request))
    return mapNovel(result.data)
}

export const updateNovel = async (novelId : string, request : NovelType.UpdateNovel) : Promise<NovelType.Novel> => {
    const result = await client.patch(`/novels/${novelId}`, mapUpdateNovelRequest(request))
    return mapNovel(result.data)
}

export const getChaptersByNovel = async (novelId : string, start? : number, end? : number) : Promise<NovelType.Chapter[]> => {
    const result = await client.get('/chapters', {
        params: {
            'novel-id': novelId,
            start,
            end
        }
    })
    return result.data.map(mapChapter)
}

export const getChapterById = async (chapterId : string) : Promise<NovelType.Chapter> => {
    const result = await client.get(`/chapters/${chapterId}`)
    return mapChapter(result.data)
}

export const createChapterForNovel = async (novelId : string, request : NovelType.CreateChapter) : Promise<NovelType.ChapterData> => {
    const result = await client.post(`/novels/${novelId}/chapters`, mapCreateChapterRequest(request))
    return mapChapterData(result.data)
}

export const updateChapter = async (chapterId : string, request : NovelType.UpdateChapter) : Promise<NovelType.Chapter> => {
    const result = await client.patch(`/chapters/${chapterId}`, mapUpdateChapterRequest(request))
    return mapChapter(result.data)
}

export const deleteChapter = async (chapterId : string) : Promise<NovelType.OperationStatus> => {
    const result = await client.delete(`/chapters/${chapterId}`)
    return mapOperationStatus(result.data)
}

export const publishChapter = async (chapterId : string) : Promise<NovelType.Chapter> => {
    const result = await client.post(`/chapters/${chapterId}/publish`)
    return mapChapter(result.data)
}

export const getChapterContent = async (chapterId : string) : Promise<NovelType.ChapterContent> => {
    const result = await client.get(`/chapters/${chapterId}/content`)
    return mapChapterContent(result.data)
}

export const getChapterContentById = async (chapterContentId : string) : Promise<NovelType.ChapterContent> => {
    const result = await client.get(`/chapter-contents/${chapterContentId}`)
    return mapChapterContent(result.data)
}

export const getChapterContentVersions = async (chapterId : string) : Promise<NovelType.ChapterContentMeta[]> => {
    const result = await client.get(`/chapters/${chapterId}/content-versions`)
    return result.data.map(mapChapterContentMeta)
}

export const getChapterContentStatus = async (
    chapterId : string,
    chapterContentId : string
) : Promise<NovelType.OperationStatus> => {
    const result = await client.get(`/chapters/${chapterId}/content-status/${chapterContentId}`)
    return mapOperationStatus(result.data)
}

export const updateChapterContent = async (
    chapterId : string,
    request : NovelType.UpdateChapterContent
) : Promise<NovelType.OperationStatus> => {
    const result = await client.patch(`/chapters/${chapterId}/content`, mapUpdateChapterContentRequest(request))
    return mapOperationStatus(result.data)
}
