import client from './client'
import * as TranslationType from '../types/translation'

// --- Response mappers (API snake_case → frontend camelCase) ---

/* eslint-disable @typescript-eslint/no-explicit-any */

export const mapChapterMapping = (data: any): TranslationType.ChapterTranslationMapping => ({
    mappingId: data.mapping_id,
    jobId: data.job_id,
    sourceChapterId: data.source_chapter_id,
    targetChapterId: data.target_chapter_id,
    status: data.status,
    mappingMessage: data.mapping_message,
})

export const mapTranslationJob = (data: any): TranslationType.NovelTranslationJob => ({
    jobId: data.job_id,
    sourceNovelId: data.source_novel_id,
    targetNovelId: data.target_novel_id,
    glossaryId: data.glossary_id,
    status: data.status,
    jobModelName: data.job_model_name,
    jobLastJobId: data.job_last_job_id,
    jobMessage: data.job_message,
    chaptersTranslated: data.chapters_translated,
    chaptersTotal: data.chapters_total,
    targetLanguageCode: data.target_language_code,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
    chapterMappings: (data.chapter_mappings_with_job || []).map(mapChapterMapping),
})

/* eslint-enable @typescript-eslint/no-explicit-any */

// --- API functions ---

export const createNovelTranslation = async (
    request: TranslationType.CreateNovelTranslation
): Promise<TranslationType.NovelTranslationJob> => {
    const response = await client.post('/translations', {
        source_novel_id: request.sourceNovelId,
        glossary_id: request.glossaryId ?? null,
        target_language_code: request.targetLanguageCode,
        model_name: request.modelName ?? null,
    })
    return mapTranslationJob(response.data)
}

export const getNovelTranslationJob = async (
    jobId: string
): Promise<TranslationType.NovelTranslationJob> => {
    const response = await client.get(`/translations/${jobId}`)
    return mapTranslationJob(response.data)
}

export const getNovelTranslationJobs = async (
    sourceNovelId: string
): Promise<TranslationType.NovelTranslationJob[]> => {
    const response = await client.get('/translations', {
        params: { 'source-novel-id': sourceNovelId }
    })
    return response.data.map(mapTranslationJob)
}
