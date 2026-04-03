// --- Glossary ---

export const GlossaryRole = {
    owner : 'owner',
    editor : 'editor',
    viewer : 'viewer',
} as const

export type GlossaryRole = (typeof GlossaryRole)[keyof typeof GlossaryRole]

export interface Glossary {
    glossaryId : string
    glossaryName : string
    glossaryDescription : string | null
    novelId : string
    sourceLanguageCode : string
    targetLanguageCode : string
}

export interface CreateGlossary {
    glossaryName : string
    glossaryDescription? : string | null
    novelId : string
    sourceLanguageCode : string
    targetLanguageCode : string
}

export interface UpdateGlossary {
    glossaryName? : string | null
    glossaryDescription? : string | null
}

// --- Glossary Entry ---

export interface GlossaryEntry {
    glossaryEntryId : string
    glossaryId : string
    sourceTerm : string
    translatedTerm : string | null
    contextNotes : string | null
    entityType : string
}

export interface CreateGlossaryEntry {
    glossaryId : string
    sourceTerm : string
    translatedTerm? : string | null
    contextNotes? : string | null
    entityType? : string
}

export interface UpdateGlossaryEntry {
    translatedTerm? : string | null
    contextNotes? : string | null
    entityType? : string | null
}

// --- Glossary Contributor ---

export interface GlossaryContributor {
    glossaryId : string
    userId : string
    glossaryContributorRole : GlossaryRole
}

export interface AddGlossaryContributor {
    userId : string
    glossaryContributorRole : GlossaryRole
}

export interface UpdateGlossaryContributor {
    glossaryContributorRole : GlossaryRole
}

// --- Term Search ---

export interface TermPosition {
    start: number
    end: number
}

export interface TermOccurrence {
    chapterId: string
    chapterNum: number
    revisionTextId: string
    positions: TermPosition[]
}

export interface SearchTermRequest {
    mode: 'string' | 'label'
    labelGroupId?: string | null
}

export interface SearchTermResponse {
    occurrences: TermOccurrence[]
    totalCount: number
}

// --- Import ---

export interface ImportFromLabels {
    labelGroupId : string
    entityTypes? : string[] | null
    overwriteExisting : boolean
}

export interface ImportResult {
    entriesCreated : number
    entriesUpdated : number
    entriesSkipped : number
}

// --- Translation Job ---

export const TranslationJobStatus = {
    pending: 'pending',
    processing: 'processing',
    done: 'done',
    failed: 'failed',
} as const

export type TranslationJobStatus = (typeof TranslationJobStatus)[keyof typeof TranslationJobStatus]

export interface GlossaryTranslationJob {
    jobId : string
    glossaryId : string
    status : TranslationJobStatus
    jobModelName : string | null
    jobLastJobId : string | null
    jobMessage : string | null
    entriesTranslated : number
    entriesTotal : number
    createdAt : string
    updatedAt : string
}

export interface CreateTranslationJob {
    modelName? : string | null
}
