import { makeAxiosError } from './testUtils'
import { vi } from 'vitest'
import client from '../client'
import {
    createNovelTranslation,
    getNovelTranslationJob,
    getNovelTranslationJobs,
} from '../translations'
import {
    type NovelTranslationJob,
    type ChapterTranslationMapping,
} from '../../types/translation'

vi.mock('../client')

describe('Translations API', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    // --- createNovelTranslation ---

    describe('createNovelTranslation', () => {
        const mockJobResponse = {
            job_id: 'uuid-job-1',
            source_novel_id: 'uuid-novel-1',
            target_novel_id: null,
            glossary_id: null,
            status: 'pending',
            job_model_name: null,
            job_last_job_id: null,
            job_message: null,
            chapters_translated: 0,
            chapters_total: 3,
            target_language_code: 'en',
            created_at: '2026-04-01T00:00:00Z',
            updated_at: '2026-04-01T00:00:00Z',
            chapter_mappings_with_job: [],
        }

        it('should call POST /translations', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: mockJobResponse })

            await createNovelTranslation({
                sourceNovelId: 'uuid-novel-1',
                targetLanguageCode: 'en',
            })

            expect(client.post).toHaveBeenCalledWith(
                '/translations',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: mockJobResponse })

            await createNovelTranslation({
                sourceNovelId: 'uuid-novel-1',
                targetLanguageCode: 'en',
            })

            expect(client.post).toHaveBeenCalledWith('/translations', {
                source_novel_id: 'uuid-novel-1',
                glossary_id: null,
                target_language_code: 'en',
                model_name: null,
            })
        })

        it('should include glossary_id and model_name in snake_case body when provided', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: mockJobResponse })

            await createNovelTranslation({
                sourceNovelId: 'uuid-novel-1',
                targetLanguageCode: 'en',
                glossaryId: 'uuid-glossary-1',
                modelName: 'gpt-4o',
            })

            expect(client.post).toHaveBeenCalledWith('/translations', {
                source_novel_id: 'uuid-novel-1',
                glossary_id: 'uuid-glossary-1',
                target_language_code: 'en',
                model_name: 'gpt-4o',
            })
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    job_id: 'uuid-job-2',
                    source_novel_id: 'uuid-novel-2',
                    target_novel_id: null,
                    glossary_id: 'uuid-glossary-1',
                    status: 'pending',
                    job_model_name: 'gpt-4o',
                    job_last_job_id: 'uuid-job-2',
                    job_message: null,
                    chapters_translated: 0,
                    chapters_total: 5,
                    target_language_code: 'en',
                    created_at: '2026-04-01T12:00:00Z',
                    updated_at: '2026-04-01T12:00:00Z',
                    chapter_mappings_with_job: [],
                }
            })

            const result = await createNovelTranslation({
                sourceNovelId: 'uuid-novel-2',
                targetLanguageCode: 'en',
                glossaryId: 'uuid-glossary-1',
                modelName: 'gpt-4o',
            })

            expectTypeOf(result).toEqualTypeOf<NovelTranslationJob>()
            expect(result).toEqual({
                jobId: 'uuid-job-2',
                sourceNovelId: 'uuid-novel-2',
                targetNovelId: null,
                glossaryId: 'uuid-glossary-1',
                status: 'pending',
                jobModelName: 'gpt-4o',
                jobLastJobId: 'uuid-job-2',
                jobMessage: null,
                chaptersTranslated: 0,
                chaptersTotal: 5,
                targetLanguageCode: 'en',
                createdAt: '2026-04-01T12:00:00Z',
                updatedAt: '2026-04-01T12:00:00Z',
                chapterMappings: [],
            } satisfies NovelTranslationJob)
        })

        it('should propagate 404 when source novel not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Source novel not found.' })
            )

            await expect(
                createNovelTranslation({ sourceNovelId: 'uuid-novel-999', targetLanguageCode: 'en' })
            ).rejects.toThrow()
        })
    })

    // --- getNovelTranslationJob ---

    describe('getNovelTranslationJob', () => {
        const mockMappingResponse = {
            mapping_id: 'uuid-map-1',
            job_id: 'uuid-job-1',
            source_chapter_id: 'uuid-ch-1',
            target_chapter_id: null,
            status: 'done',
            mapping_message: null,
        }

        const mockJobWithMappings = {
            job_id: 'uuid-job-1',
            source_novel_id: 'uuid-novel-1',
            target_novel_id: null,
            glossary_id: null,
            status: 'done',
            job_model_name: null,
            job_last_job_id: null,
            job_message: null,
            chapters_translated: 1,
            chapters_total: 1,
            target_language_code: 'en',
            created_at: '2026-04-01T00:00:00Z',
            updated_at: '2026-04-01T01:00:00Z',
            chapter_mappings_with_job: [mockMappingResponse],
        }

        it('should call GET /translations/{jobId}', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: mockJobWithMappings })

            await getNovelTranslationJob('uuid-job-1')

            expect(client.get).toHaveBeenCalledWith('/translations/uuid-job-1')
        })

        it('should map response from snake_case to camelCase including nested chapter_mappings_with_job', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    job_id: 'uuid-job-3',
                    source_novel_id: 'uuid-novel-3',
                    target_novel_id: 'uuid-novel-4',
                    glossary_id: 'uuid-glossary-2',
                    status: 'done',
                    job_model_name: 'gpt-4o',
                    job_last_job_id: 'uuid-job-3',
                    job_message: null,
                    chapters_translated: 2,
                    chapters_total: 2,
                    target_language_code: 'zh',
                    created_at: '2026-04-02T00:00:00Z',
                    updated_at: '2026-04-02T02:00:00Z',
                    chapter_mappings_with_job: [
                        {
                            mapping_id: 'uuid-map-10',
                            job_id: 'uuid-job-3',
                            source_chapter_id: 'uuid-ch-10',
                            target_chapter_id: 'uuid-ch-20',
                            status: 'done',
                            mapping_message: null,
                        },
                        {
                            mapping_id: 'uuid-map-11',
                            job_id: 'uuid-job-3',
                            source_chapter_id: 'uuid-ch-11',
                            target_chapter_id: null,
                            status: 'skipped',
                            mapping_message: 'Chapter was empty',
                        },
                    ],
                }
            })

            const result = await getNovelTranslationJob('uuid-job-3')

            expectTypeOf(result).toEqualTypeOf<NovelTranslationJob>()
            expect(result).toEqual({
                jobId: 'uuid-job-3',
                sourceNovelId: 'uuid-novel-3',
                targetNovelId: 'uuid-novel-4',
                glossaryId: 'uuid-glossary-2',
                status: 'done',
                jobModelName: 'gpt-4o',
                jobLastJobId: 'uuid-job-3',
                jobMessage: null,
                chaptersTranslated: 2,
                chaptersTotal: 2,
                targetLanguageCode: 'zh',
                createdAt: '2026-04-02T00:00:00Z',
                updatedAt: '2026-04-02T02:00:00Z',
                chapterMappings: [
                    {
                        mappingId: 'uuid-map-10',
                        jobId: 'uuid-job-3',
                        sourceChapterId: 'uuid-ch-10',
                        targetChapterId: 'uuid-ch-20',
                        status: 'done',
                        mappingMessage: null,
                    },
                    {
                        mappingId: 'uuid-map-11',
                        jobId: 'uuid-job-3',
                        sourceChapterId: 'uuid-ch-11',
                        targetChapterId: null,
                        status: 'skipped',
                        mappingMessage: 'Chapter was empty',
                    },
                ],
            } satisfies NovelTranslationJob)
        })

        it('should return empty chapterMappings array when chapter_mappings_with_job is absent', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    job_id: 'uuid-job-4',
                    source_novel_id: 'uuid-novel-4',
                    target_novel_id: null,
                    glossary_id: null,
                    status: 'pending',
                    job_model_name: null,
                    job_last_job_id: null,
                    job_message: null,
                    chapters_translated: 0,
                    chapters_total: 0,
                    target_language_code: 'en',
                    created_at: '2026-04-03T00:00:00Z',
                    updated_at: '2026-04-03T00:00:00Z',
                    // no chapter_mappings_with_job key
                }
            })

            const result = await getNovelTranslationJob('uuid-job-4')

            expect(result.chapterMappings).toEqual([])
        })

        it('should map each chapter mapping to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    ...mockJobWithMappings,
                    chapter_mappings_with_job: [mockMappingResponse],
                }
            })

            const result = await getNovelTranslationJob('uuid-job-1')

            expectTypeOf(result.chapterMappings).toEqualTypeOf<ChapterTranslationMapping[]>()
            expect(result.chapterMappings[0]).toEqual({
                mappingId: 'uuid-map-1',
                jobId: 'uuid-job-1',
                sourceChapterId: 'uuid-ch-1',
                targetChapterId: null,
                status: 'done',
                mappingMessage: null,
            } satisfies ChapterTranslationMapping)
        })

        it('should propagate 404 when job not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Translation job not found.' })
            )

            await expect(getNovelTranslationJob('uuid-job-999')).rejects.toThrow()
        })
    })

    // --- getNovelTranslationJobs ---

    describe('getNovelTranslationJobs', () => {
        it('should call GET /translations with source-novel-id query param', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getNovelTranslationJobs('uuid-novel-1')

            expect(client.get).toHaveBeenCalledWith('/translations', {
                params: { 'source-novel-id': 'uuid-novel-1' }
            })
        })

        it('should map array of jobs from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        job_id: 'uuid-job-10',
                        source_novel_id: 'uuid-novel-1',
                        target_novel_id: null,
                        glossary_id: null,
                        status: 'done',
                        job_model_name: 'default-model',
                        job_last_job_id: 'uuid-job-10',
                        job_message: null,
                        chapters_translated: 5,
                        chapters_total: 5,
                        target_language_code: 'en',
                        created_at: '2026-04-01T10:00:00Z',
                        updated_at: '2026-04-01T11:00:00Z',
                        chapter_mappings_with_job: [],
                    },
                    {
                        job_id: 'uuid-job-11',
                        source_novel_id: 'uuid-novel-1',
                        target_novel_id: null,
                        glossary_id: 'uuid-g-1',
                        status: 'failed',
                        job_model_name: 'gpt-4o',
                        job_last_job_id: 'uuid-job-11',
                        job_message: 'Translation failed: timeout',
                        chapters_translated: 2,
                        chapters_total: 5,
                        target_language_code: 'en',
                        created_at: '2026-04-02T10:00:00Z',
                        updated_at: '2026-04-02T10:05:00Z',
                        chapter_mappings_with_job: [],
                    },
                ]
            })

            const result = await getNovelTranslationJobs('uuid-novel-1')

            expectTypeOf(result).toEqualTypeOf<NovelTranslationJob[]>()
            expect(result).toEqual([
                {
                    jobId: 'uuid-job-10',
                    sourceNovelId: 'uuid-novel-1',
                    targetNovelId: null,
                    glossaryId: null,
                    status: 'done',
                    jobModelName: 'default-model',
                    jobLastJobId: 'uuid-job-10',
                    jobMessage: null,
                    chaptersTranslated: 5,
                    chaptersTotal: 5,
                    targetLanguageCode: 'en',
                    createdAt: '2026-04-01T10:00:00Z',
                    updatedAt: '2026-04-01T11:00:00Z',
                    chapterMappings: [],
                },
                {
                    jobId: 'uuid-job-11',
                    sourceNovelId: 'uuid-novel-1',
                    targetNovelId: null,
                    glossaryId: 'uuid-g-1',
                    status: 'failed',
                    jobModelName: 'gpt-4o',
                    jobLastJobId: 'uuid-job-11',
                    jobMessage: 'Translation failed: timeout',
                    chaptersTranslated: 2,
                    chaptersTotal: 5,
                    targetLanguageCode: 'en',
                    createdAt: '2026-04-02T10:00:00Z',
                    updatedAt: '2026-04-02T10:05:00Z',
                    chapterMappings: [],
                },
            ] satisfies NovelTranslationJob[])
        })

        it('should return empty array when backend returns empty array', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            const result = await getNovelTranslationJobs('uuid-novel-99')

            expect(result).toEqual([])
        })

        it('should propagate 401 when unauthenticated', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(401, { detail: 'Not authenticated' })
            )

            await expect(getNovelTranslationJobs('uuid-novel-1')).rejects.toThrow()
        })
    })
})
