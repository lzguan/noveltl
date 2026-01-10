export const Visibility = {
    private : 0,
    restricted : 1,
    unlisted : 2,
    public : 3
} as const

export type Visibility = (typeof Visibility)[keyof typeof Visibility]

export type Role = 'owner' | 'viewer' | 'editor'

export type NovelType = 'original' | 'translation' | 'other'

export interface Novel {
    novel_id : number
    novel_title : string
    novel_description? : string
    novel_author? : string
    novel_visibility : Visibility
    novel_type : NovelType
    novel_parent_id? : number
    language_id : number
}

export interface CreateNovel {
    novel_title : string
    novel_description? : string
    novel_author? : string
    novel_visibility : Visibility
    novel_type : NovelType
    language_id : number
}

export interface UpdateNovel {
    novel_title? : string
    novel_description? : string
    novel_author? : string
    novel_visibility? : Visibility
    novel_type? : NovelType
    novel_parent_id? : number
}

export interface RawChapter {
    raw_chapter_id : number
    raw_chapter_num : number
    novel_id : number
}

export interface CreateRawChapter {
    raw_chapter_num : number
}

export interface RawChapterRevision {
    raw_chapter_revision_id : number
    raw_chapter_revision_title : string
    raw_chapter_revision_is_primary : boolean
    raw_chapter_revision_is_public : boolean
    raw_chapter_revision_is_final : boolean
    raw_chapter_id : number
    raw_chapter_revision_text : string
}

export type RawChapterRevisionMeta = Omit<RawChapterRevision, 'raw_chapter_revision_text'>

export interface CreateRawChapterRevision {
    raw_chapter_revision_title : string
    raw_chapter_revision_text? : string
}

export interface UpdateRawChapterRevision {
    raw_chapter_revision_title? : string
    raw_chapter_revision_text? : string
}

export interface DeleteRawChapterRevisionStatus {
    status : 'success' | 'fail'
    detail? : string
}