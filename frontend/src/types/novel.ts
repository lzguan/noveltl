export const Visibility = {
    private : 0,
    restricted : 1,
    unlisted : 2,
    public : 3
} as const

export type Visibility = (typeof Visibility)[keyof typeof Visibility]

export type Role = 'owner' | 'viewer' | 'editor'

export type NovelType = 'original' | 'translation' | 'other'

export interface SourceWork {
    sourceWorkId : string
    sourceWorkTitle : string
    sourceWorkDescription : string | null
}

export interface CreateSourceWork {
    sourceWorkTitle : string
    sourceWorkDescription? : string
}

export interface UpdateSourceWork {
    sourceWorkTitle? : string
    sourceWorkDescription? : string
}

export interface Novel {
    novelId : string
    novelTitle : string
    novelDescription : string | null
    novelAuthor : string | null
    novelVisibility : Visibility
    novelType : NovelType
    languageCode : string
}

export interface CreateNovel {
    novelTitle : string
    novelDescription? : string
    novelAuthor? : string
    novelVisibility : Visibility
    novelType : NovelType
    languageCode : string
    sourceWorkId? : string | null
}

export interface UpdateNovel {
    novelTitle? : string
    novelDescription? : string
    novelAuthor? : string
    novelVisibility? : Visibility
    novelType? : NovelType
}

export interface Chapter {
    chapterId : string
    chapterNum : number
    chapterTitle : string
    chapterIsPublic : boolean
    novelId : string
}

export interface CreateChapter {
    chapterNum : number
    chapterTitle? : string
    chapterIsPublic? : boolean
}

export interface UpdateChapter {
    chapterTitle : string
}

export interface ChapterContent {
    chapterContentText : string
    chapterContentVersion : number
    chapterContentId : string
}

export interface ChapterContentMeta {
    chapterContentVersion : number
    chapterContentId : string
}

export interface ChapterData {
    metadata : Chapter
    content : ChapterContent
}

export interface TextOp {
    op : 'insert' | 'delete'
    start : number
    text : string
}

export interface UpdateChapterContent {
    textOps : TextOp[]
    chapterContentId : string
}

export interface OperationStatus {
    status : 'success' | 'fail'
    detail? : string | null
}
