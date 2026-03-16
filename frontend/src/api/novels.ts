import client from './client'
import * as NovelType from '../types/novel'

// --- Response mappers (API snake_case → frontend camelCase) ---

/* eslint-disable @typescript-eslint/no-explicit-any */

const mapNovel = (data: any): NovelType.Novel => ({
    novelId: data.novel_id,
    novelTitle: data.novel_title,
    novelDescription: data.novel_description,
    novelAuthor: data.novel_author,
    novelVisibility: data.novel_visibility,
    novelType: data.novel_type,
    novelParentId: data.novel_parent_id,
    languageCode: data.language_code,
})

const mapRawChapter = (data: any): NovelType.RawChapter => ({
    rawChapterId: data.raw_chapter_id,
    rawChapterNum: data.raw_chapter_num,
    novelId: data.novel_id,
})

const mapRevision = (data: any): NovelType.RawChapterRevision => ({
    rawChapterRevisionId: data.raw_chapter_revision_id,
    rawChapterRevisionTitle: data.raw_chapter_revision_title,
    rawChapterRevisionIsPrimary: data.raw_chapter_revision_is_primary,
    rawChapterRevisionIsPublic: data.raw_chapter_revision_is_public,
    rawChapterRevisionIsFinal: data.raw_chapter_revision_is_final,
    rawChapterId: data.raw_chapter_id,
    rawChapterRevisionText: data.raw_chapter_revision_text,
})

const mapRevisionMeta = (data: any): NovelType.RawChapterRevisionMeta => ({
    rawChapterRevisionId: data.raw_chapter_revision_id,
    rawChapterRevisionTitle: data.raw_chapter_revision_title,
    rawChapterRevisionIsPrimary: data.raw_chapter_revision_is_primary,
    rawChapterRevisionIsPublic: data.raw_chapter_revision_is_public,
    rawChapterRevisionIsFinal: data.raw_chapter_revision_is_final,
    rawChapterId: data.raw_chapter_id,
})

// --- Request mappers (frontend camelCase → API snake_case) ---

const mapCreateNovelRequest = (data: NovelType.CreateNovel) => ({
    novel_title: data.novelTitle,
    novel_description: data.novelDescription,
    novel_author: data.novelAuthor,
    novel_visibility: data.novelVisibility,
    novel_type: data.novelType,
    language_code: data.languageCode,
})

const mapCreateRawChapterRequest = (data: NovelType.CreateRawChapter) => ({
    raw_chapter_num: data.rawChapterNum,
})

const mapCreateRevisionRequest = (data: NovelType.CreateRawChapterRevision) => ({
    raw_chapter_revision_title: data.rawChapterRevisionTitle,
    raw_chapter_revision_text: data.rawChapterRevisionText,
})

const mapUpdateNovelRequest = (data: NovelType.UpdateNovel) => ({
    novel_title: data.novelTitle,
    novel_description: data.novelDescription,
    novel_author: data.novelAuthor,
    novel_visibility: data.novelVisibility,
    novel_type: data.novelType,
    novel_parent_id: data.novelParentId,
})

const mapUpdateRevisionRequest = (data: NovelType.UpdateRawChapterRevision) => ({
    raw_chapter_revision_title: data.rawChapterRevisionTitle,
    raw_chapter_revision_text: data.rawChapterRevisionText,
})

const mapDeleteRevisionStatus = (data: any): NovelType.DeleteRawChapterRevisionStatus => ({
    status: data.status,
    detail: data.detail,
})

/* eslint-enable @typescript-eslint/no-explicit-any */

// --- API functions ---

export const getNovels = async (titleContains? : string) : Promise<NovelType.Novel[]> => {
    const result = await client.get('/novels', {
        params : {
            "title-contains": titleContains
        }
    })
    return result.data.map(mapNovel)
}

export const getNovelsMine = async (editable : boolean, titleContains? : string) : Promise<NovelType.Novel[]> => {
    const result = await client.get('/novels/mine', {
        params : {
            editable,
            "title-contains": titleContains
        }
    })
    return result.data.map(mapNovel)
}

export const getNovelById = async (novelId : number) : Promise<NovelType.Novel> => {
    const result = await client.get(`/novels/${novelId}`)
    return mapNovel(result.data)
}

export const getChaptersByNovel = async (novelId : number, start? : number, end? : number) : Promise<NovelType.RawChapter[]> => {
    const result = await client.get(`/chapters`, {
        params : {
            "novel-id": novelId,
            start,
            end
        }
    })
    return result.data.map(mapRawChapter)
}

export const getChapterById = async (chapterId : number) : Promise<NovelType.RawChapter> => {
    const result = await client.get(`/chapters/${chapterId}`)
    return mapRawChapter(result.data)
}

export const getChapterRevisionById = async (revisionId : number) : Promise<NovelType.RawChapterRevision> => {
    const result = await client.get(`/revisions/${revisionId}`)
    return mapRevision(result.data)
}

export const getChapterRevisionsByNovel = async (
    novelId : number,
    start? : number,
    end? : number,
    isPublic? : boolean,
    isPrimary? : boolean,
    isFinal? : boolean
) : Promise<NovelType.RawChapterRevisionMeta[]> => {
    const result = await client.get(`/novels/${novelId}/revisions`, {
        params : {
            start,
            end,
            "is-public": isPublic,
            "is-primary": isPrimary,
            "is-final": isFinal
        }
    })
    return result.data.map(mapRevisionMeta)
}

export const getChapterRevisionsByChapter = async (
    chapterId : number,
    isPublic? : boolean,
    isPrimary? : boolean
) : Promise<NovelType.RawChapterRevisionMeta[]> => {
    const result = await client.get(`/chapters/${chapterId}/revisions`, {
        params : {
            "is-public": isPublic,
            "is-primary": isPrimary
        }
    })
    return result.data.map(mapRevisionMeta)
}

export const createNovel = async (request : NovelType.CreateNovel) : Promise<NovelType.Novel> => {
    const result = await client.post(`/novels`, mapCreateNovelRequest(request))
    return mapNovel(result.data)
}

export const createChapterForNovel = async (novelId : number, request : NovelType.CreateRawChapter) : Promise<NovelType.RawChapter> => {
    const result = await client.post(`/novels/${novelId}/chapters`, mapCreateRawChapterRequest(request))
    return mapRawChapter(result.data)
}

export const createRevisionForChapter = async (chapterId : number, request : NovelType.CreateRawChapterRevision) : Promise<NovelType.RawChapterRevision> => {
    const result = await client.post(`/chapters/${chapterId}/revisions`, mapCreateRevisionRequest(request))
    return mapRevision(result.data)
}

export const updateNovel = async (novelId : number, request : NovelType.UpdateNovel) : Promise<NovelType.Novel> => {
    const result = await client.patch(`/novels/${novelId}`, mapUpdateNovelRequest(request))
    return mapNovel(result.data)
}

export const updateRevision = async (revisionId : number, request : NovelType.UpdateRawChapterRevision) : Promise<NovelType.RawChapterRevision> => {
    const result = await client.patch(`/revisions/${revisionId}`, mapUpdateRevisionRequest(request))
    return mapRevision(result.data)
}

export const publishRevision = async (revisionId : number) : Promise<NovelType.RawChapterRevision> => {
    const result = await client.post(`/revisions/${revisionId}/publish`)
    return mapRevision(result.data)
}

export const makeRevisionPrimary = async (revisionId : number) : Promise<NovelType.RawChapterRevision> => {
    const result = await client.post(`/revisions/${revisionId}/make-primary`)
    return mapRevision(result.data)
}

export const finalizeRevision = async (revisionId : number) : Promise<NovelType.RawChapterRevision> => {
    const result = await client.post(`/revisions/${revisionId}/finalize`)
    return mapRevision(result.data)
}

export const deleteRevision = async (revisionId : number) : Promise<NovelType.DeleteRawChapterRevisionStatus> => {
    const result = await client.delete(`/revisions/${revisionId}`)
    return mapDeleteRevisionStatus(result.data)
}
