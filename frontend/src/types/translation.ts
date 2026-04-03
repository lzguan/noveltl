// --- Novel Translation Job ---

export const NovelTranslationStatus = {
    pending: 'pending',
    processing: 'processing',
    done: 'done',
    failed: 'failed',
} as const

export type NovelTranslationStatus = (typeof NovelTranslationStatus)[keyof typeof NovelTranslationStatus]

export const ChapterTranslationStatus = {
    pending: 'pending',
    processing: 'processing',
    done: 'done',
    failed: 'failed',
    skipped: 'skipped',
} as const

export type ChapterTranslationStatus = (typeof ChapterTranslationStatus)[keyof typeof ChapterTranslationStatus]

export interface ChapterTranslationMapping {
    mappingId: string
    jobId: string
    sourceChapterId: string
    targetChapterId: string | null
    status: ChapterTranslationStatus
    mappingMessage: string | null
}

export interface NovelTranslationJob {
    jobId: string
    sourceNovelId: string
    targetNovelId: string | null
    glossaryId: string | null
    status: NovelTranslationStatus
    jobModelName: string
    jobLastJobId: string
    jobMessage: string | null
    chaptersTranslated: number
    chaptersTotal: number
    targetLanguageCode: string
    createdAt: string
    updatedAt: string
    chapterMappings: ChapterTranslationMapping[]
}

export interface CreateNovelTranslation {
    sourceNovelId: string
    glossaryId?: string | null
    targetLanguageCode: string
    modelName?: string | null
}
