import { makeAxiosError } from './testUtils'
import { vi } from 'vitest'
import client from '../client'
import {
    getLabelGroupsByNovel,
    createLabelGroup,
    getLabelGroupById
} from '../labels'
import { type LabelGroup } from '../../types/label'

vi.mock('../client')

describe('Labels API', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('getLabelGroupsByNovel', () => {
        it('should call GET /label-groups with novel-id query param', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getLabelGroupsByNovel(5)

            expect(client.get).toHaveBeenCalledWith('/label-groups', {
                params: { 'novel-id': 5 }
            })
        })

        it('should map each label group from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    { label_group_id: 1, label_group_name: 'Group 1', novel_id: 5 },
                    { label_group_id: 2, label_group_name: 'Group 2', novel_id: 5 }
                ]
            })

            const result = await getLabelGroupsByNovel(5)

            expectTypeOf(result).toEqualTypeOf<LabelGroup[]>()
            expect(result).toEqual([
                { labelGroupId: 1, labelGroupName: 'Group 1', novelId: 5 },
                { labelGroupId: 2, labelGroupName: 'Group 2', novelId: 5 }
            ] satisfies LabelGroup[])
        })

        it('should return empty array when backend returns empty array', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            const result = await getLabelGroupsByNovel(10)

            expect(result).toEqual([])
        })
    })

    describe('createLabelGroup', () => {
        it('should call POST /label-groups', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { label_group_id: 1, label_group_name: 'New Group', novel_id: 3 }
            })

            await createLabelGroup({ labelGroupName: 'New Group', novelId: 3 })

            expect(client.post).toHaveBeenCalled()
            expect(client.post).toHaveBeenCalledWith(
                '/label-groups',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { label_group_id: 2, label_group_name: 'My Labels', novel_id: 7 }
            })

            await createLabelGroup({ labelGroupName: 'My Labels', novelId: 7 })

            expect(client.post).toHaveBeenCalledWith('/label-groups', {
                label_group_name: 'My Labels',
                novel_id: 7
            })
        })

        it('should map label group response to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { label_group_id: 10, label_group_name: 'Test Group', novel_id: 15 }
            })

            const result = await createLabelGroup({
                labelGroupName: 'Test Group',
                novelId: 15
            })

            expectTypeOf(result).toEqualTypeOf<LabelGroup>()
            expect(result).toEqual({
                labelGroupId: 10,
                labelGroupName: 'Test Group',
                novelId: 15
            } satisfies LabelGroup)
        })

        it('should propagate 404 error when novel not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(createLabelGroup({
                labelGroupName: 'Group',
                novelId: 999
            })).rejects.toThrow()
        })

        it('should propagate 400 error when data too long', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Label group name too long' })
            )

            await expect(createLabelGroup({
                labelGroupName: 'G'.repeat(10000),
                novelId: 5
            })).rejects.toThrow()
        })
    })

    describe('getLabelGroupById', () => {
        it('should call GET /label-groups/{labelGroupId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { label_group_id: 5, label_group_name: 'Group', novel_id: 2 }
            })

            await getLabelGroupById(5)

            expect(client.get).toHaveBeenCalledWith('/label-groups/5')
        })

        it('should map label group from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { label_group_id: 20, label_group_name: 'My Group', novel_id: 8 }
            })

            const result = await getLabelGroupById(20)

            expectTypeOf(result).toEqualTypeOf<LabelGroup>()
            expect(result).toEqual({
                labelGroupId: 20,
                labelGroupName: 'My Group',
                novelId: 8
            } satisfies LabelGroup)
        })

        it('should propagate 404 error when label group not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Label group not found' })
            )

            await expect(getLabelGroupById(999)).rejects.toThrow()
        })
    })
})
