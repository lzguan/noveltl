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
    novelId : string
    novelTitle : string
    novelDescription : string | null
    novelAuthor : string | null
    novelVisibility : Visibility
    novelType : NovelType
    novelParentId : string | null
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
    novelParentId? : string
}

export interface Chapter {
    chapterId : string
    chapterNum : number
    novelId : string
}

export interface CreateChapter {
    chapterNum : number
}

export interface Revision {
    revisionId : string
    revisionTitle : string
    revisionIsPrimary : boolean
    revisionIsPublic : boolean
    chapterId : string
}

export type RevisionMeta = Revision

export interface RevisionText {
    revisionTextId : string
    revisionTextContent : string
    revisionTextVersion : number
}

export interface RevisionTextMeta {
    revisionTextId : string
    revisionTextVersion : number
}

export interface RevisionData {
    metadata : Revision
    content : RevisionText
}

export interface CreateRevision {
    revisionTitle : string
}

export interface UpdateRevision {
    revisionTitle? : string
}

export interface TextOp {
    op : 'insert' | 'delete'
    start : number
    text : string
}

export interface UpdateRevisionText {
    textOps : TextOp[]
    revisionTextId : string
}

export interface OperationStatus {
    status : 'success' | 'fail'
    detail? : string | null
}

// --- Novel Associations ---

export interface NovelAssociation {
    associationId : string
    sourceNovelId : string
    targetNovelId : string
    associationType : string
}

export interface CreateNovelAssociation {
    sourceNovelId : string
    targetNovelId : string
    associationType : string
}
