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
    novelId : number
    novelTitle : string
    novelDescription : string | null
    novelAuthor : string | null
    novelVisibility : Visibility
    novelType : NovelType
    novelParentId : number | null
    languageCode : string
}

export interface CreateNovel {
    novelTitle : string
    novelDescription? : string
    novelAuthor? : string
    novelVisibility : Visibility
    novelType : NovelType
    languageCode : string
}

export interface UpdateNovel {
    novelTitle? : string
    novelDescription? : string
    novelAuthor? : string
    novelVisibility? : Visibility
    novelType? : NovelType
    novelParentId? : number
}

export interface RawChapter {
    rawChapterId : number
    rawChapterNum : number
    novelId : number
}

export interface CreateRawChapter {
    rawChapterNum : number
}

export interface RawChapterRevision {
    rawChapterRevisionId : number
    rawChapterRevisionTitle : string
    rawChapterRevisionIsPrimary : boolean
    rawChapterRevisionIsPublic : boolean
    rawChapterRevisionIsFinal : boolean
    rawChapterId : number
    rawChapterRevisionText : string
}

export type RawChapterRevisionMeta = Omit<RawChapterRevision, 'rawChapterRevisionText'>

export interface CreateRawChapterRevision {
    rawChapterRevisionTitle : string
    rawChapterRevisionText? : string
}

export interface UpdateRawChapterRevision {
    rawChapterRevisionTitle? : string
    rawChapterRevisionText? : string
}

export interface DeleteRawChapterRevisionStatus {
    status : 'success' | 'fail'
    detail? : string
}