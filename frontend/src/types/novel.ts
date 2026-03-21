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

export interface Chapter {
    chapterId : number
    chapterNum : number
    novelId : number
}

export interface CreateChapter {
    chapterNum : number
}

export interface Revision {
    revisionId : number
    revisionTitle : string
    revisionIsPrimary : boolean
    revisionIsPublic : boolean
    revisionIsFinal : boolean
    chapterId : number
    revisionText : string
}

export type RevisionMeta = Omit<Revision, 'revisionText'>

export interface CreateRevision {
    revisionTitle : string
    revisionText? : string
}

export interface UpdateRevision {
    revisionTitle? : string
    revisionText? : string
}

export interface DeleteRevisionStatus {
    status : 'success' | 'fail'
    detail? : string
}
