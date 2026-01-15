import client from './client'
import * as NovelType from '../types/novel'

export const get_novels = async (title_contains? : string) : Promise<NovelType.Novel[]> => {
    const result = await client.get('/novels', {
        params : {
            title_contains
        }
    })
    return result.data
}

export const get_novels_mine = async (editable : boolean, titleContains? : string) : Promise<NovelType.Novel[]> => {
    const result = await client.get('/novels/mine', {
        params : {
            editable,
            titleContains
        }
    })
    return result.data
}

export const get_novel_by_id = async (novel_id : number) : Promise<NovelType.Novel> => {
    const result = await client.get(`/novels/${novel_id}`)
    return result.data
}

export const get_chapters_by_novel = async (novel_id : number, start? : number, end? : number) : Promise<NovelType.RawChapter[]> => {
    const result = await client.get(`/chapters`, {
        params : {
            novel_id,
            start,
            end
        }
    })
    return result.data
}

export const get_chapter_by_id = async (chapter_id : number) : Promise<NovelType.RawChapter> => {
    const result = await client.get(`/chapters/${chapter_id}`)
    return result.data
}

export const get_chapter_revision_by_id = async (chapter_revision_id : number) : Promise<NovelType.RawChapterRevision> => {
    const result = await client.get(`/revisions/${chapter_revision_id}`)
    return result.data
}

export const get_chapter_revisions_by_novel = async (
    novel_id : number,
    start? : number,
    end? : number,
    is_public? : boolean,
    is_primary? : boolean,
    is_final? : boolean
) : Promise<NovelType.RawChapterRevisionMeta[]> => {
    const result = await client.get(`novels/${novel_id}/revisions`, {
        params : {
            start,
            end,
            is_public,
            is_primary,
            is_final
        }
    })
    return result.data
}

export const get_chapter_revisions_by_chapter = async (
    chapter_id : number,
    is_public? : boolean,
    is_primary? : boolean
) : Promise<NovelType.RawChapterRevisionMeta[]> => {
    const result = await client.get(`chapters/${chapter_id}/revisions`, {
        params : {
            is_public,
            is_primary
        }
    })
    return result.data
}

export const create_novel = async (request : NovelType.CreateNovel) : Promise<NovelType.Novel> => {
    const result =  await client.post(`/novels`, request)
    return result.data
}

export const create_chapter = async (novel_id : number, request : NovelType.CreateRawChapter) : Promise<NovelType.RawChapter> => {
    const result = await client.post(`/novels/${novel_id}/chapters`, request)
    return result.data
}

export const create_chapter_revision = async (chapter_id : number, request : NovelType.CreateRawChapterRevision) : Promise<NovelType.RawChapterRevision> => {
    const result = await client.post(`/chapters/${chapter_id}/revisions`, request)
    return result.data
}
