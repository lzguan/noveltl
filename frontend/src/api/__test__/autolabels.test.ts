import { makeAxiosError } from './testUtils'
import { vi } from 'vitest'
import client from '../client'
import {
    getAutoLabelById,
    getAutoLabels,
    createAutoLabels
} from '../autolabels'
import { type AutoLabel, type AutoLabelMeta } from '../../types/autolabel'

vi.mock('../client')

describe('AutoLabels API', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('getAutoLabelById', () => {
        it('should call GET /auto-labels/{autoLabelId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    auto_label_id: 1,
                    auto_label_data: null,
                    auto_label_model_name: 'cluener',
                    auto_label_model_params: {},
                    auto_label_status: 'pending',
                    auto_label_message: null,
                    raw_chapter_revision_id: 10,
                    auto_label_last_job_id: 'job123'
                }
            })

            await getAutoLabelById(1)

            expect(client.get).toHaveBeenCalledWith('/auto-labels/1')
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    auto_label_id: 5,
                    auto_label_data: [
                        {
                            label_entity_group: 'PERSON',
                            label_score: 0.95,
                            label_word: 'John',
                            label_start: 0,
                            label_end: 4,
                            label_dirty: false
                        }
                    ],
                    auto_label_model_name: 'cluener',
                    auto_label_model_params: { chunk_size: 500 },
                    auto_label_status: 'done',
                    auto_label_message: 'Completed',
                    raw_chapter_revision_id: 20,
                    auto_label_last_job_id: 'job456'
                }
            })

            const result = await getAutoLabelById(5)

            expectTypeOf(result).toEqualTypeOf<AutoLabel>()
            expect(result).toEqual({
                autoLabelId: 5,
                autoLabelData: [
                    {
                        labelEntityGroup: 'PERSON',
                        labelScore: 0.95,
                        labelWord: 'John',
                        labelStart: 0,
                        labelEnd: 4,
                        labelDirty: false
                    }
                ],
                autoLabelModelName: 'cluener',
                autoLabelModelParams: { chunk_size: 500 },
                autoLabelStatus: 'done',
                autoLabelMessage: 'Completed',
                rawChapterRevisionId: 20,
                autoLabelLastJobId: 'job456'
            } satisfies AutoLabel)
        })

        it('should propagate 404 error when autolabel not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'AutoLabel not found' })
            )

            await expect(getAutoLabelById(999)).rejects.toThrow()
        })

        it('should propagate 403 error for insufficient permissions', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(403, { detail: 'Insufficient permissions' })
            )

            await expect(getAutoLabelById(10)).rejects.toThrow()
        })
    })

    describe('getAutoLabels', () => {
        it('should call GET /auto-labels with all query params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: {} })

            await getAutoLabels(5, [1, 2], [10, 20], 1, 100, ['cluener'])

            expect(client.get).toHaveBeenCalledWith('/auto-labels', {
                params: {
                    'novel-id': 5,
                    'raw-chapter-ids': [1, 2],
                    'raw-chapter-revision-ids': [10, 20],
                    start: 1,
                    end: 100,
                    'model-names': ['cluener']
                }
            })
        })

        it('should map dictionary values from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    '1': {
                        auto_label_id: 1,
                        auto_label_model_name: 'cluener',
                        auto_label_model_params: {},
                        auto_label_status: 'pending',
                        auto_label_message: null,
                        raw_chapter_revision_id: 10,
                        auto_label_last_job_id: 'job1'
                    },
                    '2': {
                        auto_label_id: 2,
                        auto_label_model_name: 'cluener',
                        auto_label_model_params: { chunk_size: 400 },
                        auto_label_status: 'done',
                        auto_label_message: 'Done',
                        raw_chapter_revision_id: 20,
                        auto_label_last_job_id: 'job2'
                    }
                }
            })

            const result = await getAutoLabels(5)

            expectTypeOf(result).toEqualTypeOf<Record<number, AutoLabelMeta>>()
            expect(result).toEqual({
                1: {
                    autoLabelId: 1,
                    autoLabelModelName: 'cluener',
                    autoLabelModelParams: {},
                    autoLabelStatus: 'pending',
                    autoLabelMessage: null,
                    rawChapterRevisionId: 10,
                    autoLabelLastJobId: 'job1'
                },
                2: {
                    autoLabelId: 2,
                    autoLabelModelName: 'cluener',
                    autoLabelModelParams: { chunk_size: 400 },
                    autoLabelStatus: 'done',
                    autoLabelMessage: 'Done',
                    rawChapterRevisionId: 20,
                    autoLabelLastJobId: 'job2'
                }
            })
        })

        it('should pass optional params as undefined when omitted', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: {} })

            await getAutoLabels(10)

            expect(client.get).toHaveBeenCalledWith('/auto-labels', {
                params: {
                    'novel-id': 10,
                    'raw-chapter-ids': undefined,
                    'raw-chapter-revision-ids': undefined,
                    start: undefined,
                    end: undefined,
                    'model-names': undefined
                }
            })
        })
    })

    describe('createAutoLabels', () => {
        it('should call POST /auto-labels', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: [] })

            await createAutoLabels({
                novelId: 5,
                autoLabelModelName: 'cluener',
                autoLabelModelParams: {}
            })

            expect(client.post).toHaveBeenCalled()
            expect(client.post).toHaveBeenCalledWith(
                '/auto-labels',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: [] })

            await createAutoLabels({
                novelId: 10,
                autoLabelModelName: 'cluener',
                autoLabelModelParams: { chunk_size: 500 },
                rawChapterIds: [1, 2, 3],
                start: 1,
                end: 10,
                isPrimary: true,
                isPublic: false
            })

            expect(client.post).toHaveBeenCalledWith('/auto-labels', {
                novel_id: 10,
                auto_label_model_name: 'cluener',
                auto_label_model_params: { chunk_size: 500 },
                raw_chapter_ids: [1, 2, 3],
                raw_chapter_revision_ids: undefined,
                start: 1,
                end: 10,
                is_primary: true,
                is_public: false
            })
        })

        it('should map response array from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: [
                    {
                        auto_label_id: 1,
                        auto_label_model_name: 'cluener',
                        auto_label_model_params: {},
                        auto_label_status: 'pending',
                        auto_label_message: null,
                        raw_chapter_revision_id: 10,
                        auto_label_last_job_id: 'job100'
                    }
                ]
            })

            const result = await createAutoLabels({
                novelId: 5,
                autoLabelModelName: 'cluener',
                autoLabelModelParams: {}
            })

            expectTypeOf(result).toEqualTypeOf<AutoLabelMeta[]>()
            expect(result).toEqual([
                {
                    autoLabelId: 1,
                    autoLabelModelName: 'cluener',
                    autoLabelModelParams: {},
                    autoLabelStatus: 'pending',
                    autoLabelMessage: null,
                    rawChapterRevisionId: 10,
                    autoLabelLastJobId: 'job100'
                }
            ] satisfies AutoLabelMeta[])
        })

        it('should propagate 400 error for duplicate autolabels', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Duplicate autolabel' })
            )

            await expect(createAutoLabels({
                novelId: 5,
                autoLabelModelName: 'cluener',
                autoLabelModelParams: {}
            })).rejects.toThrow()
        })

        it('should propagate 500 error for unknown errors', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(500, { detail: 'Unknown error' })
            )

            await expect(createAutoLabels({
                novelId: 5,
                autoLabelModelName: 'cluener',
                autoLabelModelParams: {}
            })).rejects.toThrow()
        })
    })
})
