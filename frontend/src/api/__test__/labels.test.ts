import { makeAxiosError } from './testUtils'
import { vi } from 'vitest'
import client from '../client'
import {
    getLabelGroupsByNovel,
    createLabelGroup,
    getLabelGroupById,
    createLabelDataByAutoLabel
} from '../labels'
import { type LabelGroup, type CreateLabelDataByAutoLabelStatus } from '../../types/label'

vi.mock('../client')

describe('Labels API', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('getLabelGroupsByNovel', () => {
        it('should call GET /label-groups with novel-id query param', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getLabelGroupsByNovel('uuid-novel-5')

            expect(client.get).toHaveBeenCalledWith('/label-groups', {
                params: { 'novel-id': 'uuid-novel-5' }
            })
        })

        it('should map each label group from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    { label_group_id: 'uuid-lg-1', label_group_name: 'Group 1', novel_id: 'uuid-novel-5' },
                    { label_group_id: 'uuid-lg-2', label_group_name: 'Group 2', novel_id: 'uuid-novel-5' }
                ]
            })

            const result = await getLabelGroupsByNovel('uuid-novel-5')

            expectTypeOf(result).toEqualTypeOf<LabelGroup[]>()
            expect(result).toEqual([
                { labelGroupId: 'uuid-lg-1', labelGroupName: 'Group 1', novelId: 'uuid-novel-5' },
                { labelGroupId: 'uuid-lg-2', labelGroupName: 'Group 2', novelId: 'uuid-novel-5' }
            ] satisfies LabelGroup[])
        })

        it('should return empty array when backend returns empty array', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            const result = await getLabelGroupsByNovel('uuid-novel-10')

            expect(result).toEqual([])
        })
    })

    describe('createLabelGroup', () => {
        it('should call POST /label-groups', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { label_group_id: 'uuid-lg-1', label_group_name: 'New Group', novel_id: 'uuid-novel-3' }
            })

            await createLabelGroup({ labelGroupName: 'New Group', novelId: 'uuid-novel-3' })

            expect(client.post).toHaveBeenCalled()
            expect(client.post).toHaveBeenCalledWith(
                '/label-groups',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { label_group_id: 'uuid-lg-2', label_group_name: 'My Labels', novel_id: 'uuid-novel-7' }
            })

            await createLabelGroup({ labelGroupName: 'My Labels', novelId: 'uuid-novel-7' })

            expect(client.post).toHaveBeenCalledWith('/label-groups', {
                label_group_name: 'My Labels',
                novel_id: 'uuid-novel-7'
            })
        })

        it('should map label group response to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { label_group_id: 'uuid-lg-10', label_group_name: 'Test Group', novel_id: 'uuid-novel-15' }
            })

            const result = await createLabelGroup({
                labelGroupName: 'Test Group',
                novelId: 'uuid-novel-15'
            })

            expectTypeOf(result).toEqualTypeOf<LabelGroup>()
            expect(result).toEqual({
                labelGroupId: 'uuid-lg-10',
                labelGroupName: 'Test Group',
                novelId: 'uuid-novel-15'
            } satisfies LabelGroup)
        })

        it('should propagate 404 error when novel not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(createLabelGroup({
                labelGroupName: 'Group',
                novelId: 'uuid-novel-999'
            })).rejects.toThrow()
        })

        it('should propagate 400 error when data too long', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Label group name too long' })
            )

            await expect(createLabelGroup({
                labelGroupName: 'G'.repeat(10000),
                novelId: 'uuid-novel-5'
            })).rejects.toThrow()
        })
    })

    describe('getLabelGroupById', () => {
        it('should call GET /label-groups/{labelGroupId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { label_group_id: 'uuid-lg-5', label_group_name: 'Group', novel_id: 'uuid-novel-2' }
            })

            await getLabelGroupById('uuid-lg-5')

            expect(client.get).toHaveBeenCalledWith('/label-groups/uuid-lg-5')
        })

        it('should map label group from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { label_group_id: 'uuid-lg-20', label_group_name: 'My Group', novel_id: 'uuid-novel-8' }
            })

            const result = await getLabelGroupById('uuid-lg-20')

            expectTypeOf(result).toEqualTypeOf<LabelGroup>()
            expect(result).toEqual({
                labelGroupId: 'uuid-lg-20',
                labelGroupName: 'My Group',
                novelId: 'uuid-novel-8'
            } satisfies LabelGroup)
        })

        it('should propagate 404 error when label group not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Label group not found' })
            )

            await expect(getLabelGroupById('uuid-lg-999')).rejects.toThrow()
        })
    })

    describe('createLabelDataByAutoLabel', () => {
        it('should call POST /label-groups/{labelGroupId}/label-datas/auto-labels', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { success: ['uuid-rev-1'], errors: [] }
            })

            await createLabelDataByAutoLabel('uuid-lg-1', {
                modelName: 'cluener',
                modelParams: {},
            })

            expect(client.post).toHaveBeenCalledWith(
                '/label-groups/uuid-lg-1/label-datas/auto-labels',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { success: [], errors: [] }
            })

            await createLabelDataByAutoLabel('uuid-lg-1', {
                modelName: 'cluener',
                modelParams: { chunk_size: 500 },
                chapterIds: ['uuid-ch-1', 'uuid-ch-2'],
                start: 1,
                end: 10
            })

            expect(client.post).toHaveBeenCalledWith(
                '/label-groups/uuid-lg-1/label-datas/auto-labels',
                {
                    model_name: 'cluener',
                    model_params: { chunk_size: 500 },
                    chapter_ids: ['uuid-ch-1', 'uuid-ch-2'],
                    revision_ids: undefined,
                    start: 1,
                    end: 10
                }
            )
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    success: ['uuid-rev-1', 'uuid-rev-2'],
                    errors: [['uuid-rev-3', 'Failed to process']]
                }
            })

            const result = await createLabelDataByAutoLabel('uuid-lg-1', {
                modelName: 'cluener',
                modelParams: {}
            })

            expectTypeOf(result).toEqualTypeOf<CreateLabelDataByAutoLabelStatus>()
            expect(result).toEqual({
                success: ['uuid-rev-1', 'uuid-rev-2'],
                errors: [['uuid-rev-3', 'Failed to process']]
            } satisfies CreateLabelDataByAutoLabelStatus)
        })
    })
})
