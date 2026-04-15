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
                    auto_label_id: 'uuid-al-1',
                    auto_label_data: null,
                    auto_label_model_name: 'cluener',
                    auto_label_model_params: {},
                    auto_label_status: 'pending',
                    auto_label_message: null,
                    chapter_content_id: 'uuid-cc-10',
                    auto_label_last_job_id: 'job123'
                }
            })

            await getAutoLabelById('uuid-al-1')

            expect(client.get).toHaveBeenCalledWith('/auto-labels/uuid-al-1')
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    auto_label_id: 'uuid-al-5',
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
                    chapter_content_id: 'uuid-cc-20',
                    auto_label_last_job_id: 'job456'
                }
            })

            const result = await getAutoLabelById('uuid-al-5')

            expectTypeOf(result).toEqualTypeOf<AutoLabel>()
            expect(result).toEqual({
                autoLabelId: 'uuid-al-5',
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
                chapterContentId: 'uuid-cc-20',
                autoLabelLastJobId: 'job456'
            } satisfies AutoLabel)
        })

        it('should propagate 404 error when autolabel not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'AutoLabel not found' })
            )

            await expect(getAutoLabelById('uuid-al-999')).rejects.toThrow()
        })
    })

    describe('getAutoLabels', () => {
        it('should call GET /auto-labels with all query params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getAutoLabels('uuid-novel-5', ['uuid-ch-1', 'uuid-ch-2'], 1, 100, ['cluener'])

            expect(client.get).toHaveBeenCalledWith('/auto-labels', {
                params: {
                    'novel-id': 'uuid-novel-5',
                    'chapter-ids': ['uuid-ch-1', 'uuid-ch-2'],
                    start: 1,
                    end: 100,
                    'model-names': ['cluener']
                }
            })
        })

        it('should map array values from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        auto_label_id: 'uuid-al-1',
                        auto_label_model_name: 'cluener',
                        auto_label_model_params: {},
                        auto_label_status: 'pending',
                        auto_label_message: null,
                        chapter_content_id: 'uuid-cc-10',
                        auto_label_last_job_id: 'job1'
                    }
                ]
            })

            const result = await getAutoLabels('uuid-novel-5')

            expectTypeOf(result).toEqualTypeOf<AutoLabelMeta[]>()
            expect(result).toEqual([
                {
                    autoLabelId: 'uuid-al-1',
                    autoLabelModelName: 'cluener',
                    autoLabelModelParams: {},
                    autoLabelStatus: 'pending',
                    autoLabelMessage: null,
                    chapterContentId: 'uuid-cc-10',
                    autoLabelLastJobId: 'job1'
                }
            ] satisfies AutoLabelMeta[])
        })
    })

    describe('createAutoLabels', () => {
        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: [] })

            await createAutoLabels({
                novelId: 'uuid-novel-10',
                autoLabelModelName: 'cluener',
                autoLabelModelParams: { chunk_size: 500 },
                chapterIds: ['uuid-ch-1', 'uuid-ch-2', 'uuid-ch-3'],
                start: 1,
                end: 10,
                isPublic: false
            })

            expect(client.post).toHaveBeenCalledWith('/auto-labels', {
                novel_id: 'uuid-novel-10',
                auto_label_model_name: 'cluener',
                auto_label_model_params: { chunk_size: 500 },
                chapter_ids: ['uuid-ch-1', 'uuid-ch-2', 'uuid-ch-3'],
                start: 1,
                end: 10,
                is_public: false
            })
        })

        it('should map response array from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: [
                    {
                        auto_label_id: 'uuid-al-1',
                        auto_label_model_name: 'cluener',
                        auto_label_model_params: {},
                        auto_label_status: 'pending',
                        auto_label_message: null,
                        chapter_content_id: 'uuid-cc-10',
                        auto_label_last_job_id: 'job100'
                    }
                ]
            })

            const result = await createAutoLabels({
                novelId: 'uuid-novel-5',
                autoLabelModelName: 'cluener',
                autoLabelModelParams: {}
            })

            expectTypeOf(result).toEqualTypeOf<AutoLabelMeta[]>()
            expect(result).toEqual([
                {
                    autoLabelId: 'uuid-al-1',
                    autoLabelModelName: 'cluener',
                    autoLabelModelParams: {},
                    autoLabelStatus: 'pending',
                    autoLabelMessage: null,
                    chapterContentId: 'uuid-cc-10',
                    autoLabelLastJobId: 'job100'
                }
            ] satisfies AutoLabelMeta[])
        })
    })
})
