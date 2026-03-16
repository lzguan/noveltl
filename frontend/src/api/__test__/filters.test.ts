import { makeAxiosError } from './testUtils'
import { vi } from 'vitest'
import client from '../client'
import {
    getFilterSchemas,
    flagInstances,
    getContexts,
    decideInstances,
    applyFilter
} from '../filters'
import { type SchemaInfo } from '../../types/filter'

vi.mock('../client')

describe('Filters API', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('getFilterSchemas', () => {
        it('should call GET /filters/schemas', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {}
            })

            await getFilterSchemas()

            expect(client.get).toHaveBeenCalledWith('/filters/schemas')
        })

        it('should return dictionary of schema info', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    'score_filter': {
                        instanceSchema: {},
                        contextSchema: {},
                        flagInstancesOptionsSchema: {},
                        getContextsOptionsSchema: {},
                        decideInstancesOptionsSchema: {},
                        applyFilterOptionsSchema: {}
                    }
                }
            })

            const result = await getFilterSchemas()

            expectTypeOf(result).toEqualTypeOf<Record<string, SchemaInfo>>()
            expect(result).toHaveProperty('score_filter')
        })
    })

    describe('flagInstances', () => {
        it('should call POST /filters/{filterName}/flag-instances', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: [] })

            await flagInstances('score_filter', { threshold: 0.8 })

            expect(client.post).toHaveBeenCalledWith(
                '/filters/score_filter/flag-instances',
                { threshold: 0.8 }
            )
        })

        it('should return array of flagged instances', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: [
                    { type: 'single_label', label: {}, rawChapterRevisionId: 1 },
                    { type: 'single_label', label: {}, rawChapterRevisionId: 2 }
                ]
            })

            const result = await flagInstances('score_filter', { threshold: 0.9 })

            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            expectTypeOf(result).toEqualTypeOf<any[]>()
            expect(result).toHaveLength(2)
        })

        it('should propagate 404 error when filter not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Filter not found' })
            )

            await expect(flagInstances('invalid_filter', {})).rejects.toThrow()
        })

        it('should propagate 400 error for invalid options', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Invalid options' })
            )

            await expect(flagInstances('score_filter', { bad: 'option' })).rejects.toThrow()
        })
    })

    describe('getContexts', () => {
        it('should call POST /filters/{filterName}/get-contexts with instances and options', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: [] })

            const instances = [{ type: 'single_label', label: {}, rawChapterRevisionId: 1 }]
            await getContexts('score_filter', instances, { option: 'value' })

            expect(client.post).toHaveBeenCalledWith(
                '/filters/score_filter/get-contexts',
                {
                    instances: instances,
                    options: { option: 'value' }
                }
            )
        })

        it('should return array of contexts', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: [
                    {
                        type: 'sentence',
                        text: 'This is a sentence.',
                        labelStartRel: 0,
                        labelEndRel: 4,
                        rawChapterRevisionId: 1
                    }
                ]
            })

            const result = await getContexts('score_filter', [], {})

            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            expectTypeOf(result).toEqualTypeOf<any[]>()
            expect(result).toHaveLength(1)
            expect(result[0]).toHaveProperty('type', 'sentence')
        })

        it('should propagate 404 error when filter not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Filter not found' })
            )

            await expect(getContexts('invalid', [], {})).rejects.toThrow()
        })

        it('should propagate 400 error for invalid instances', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Instance validation error' })
            )

            await expect(getContexts('score_filter', [{ invalid: true }], {})).rejects.toThrow()
        })
    })

    describe('decideInstances', () => {
        it('should call POST /filters/{filterName}/decide-instances with instance_contexts', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: [] })

            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const instanceContexts: [any, any][] = [
                [{ type: 'single_label' }, { type: 'sentence' }]
            ]
            await decideInstances('score_filter', instanceContexts, { threshold: 0.5 })

            expect(client.post).toHaveBeenCalledWith(
                '/filters/score_filter/decide-instances',
                {
                    instance_contexts: instanceContexts,
                    options: { threshold: 0.5 }
                }
            )
        })

        it('should return array of boolean decisions', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: [true, false, true]
            })

            const result = await decideInstances('score_filter', [], {})

            expectTypeOf(result).toEqualTypeOf<boolean[]>()
            expect(result).toEqual([true, false, true])
        })

        it('should propagate 404 error when filter not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Filter not found' })
            )

            await expect(decideInstances('invalid', [], {})).rejects.toThrow()
        })

        it('should propagate 400 error for validation errors', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Instance/context validation error' })
            )

            await expect(decideInstances('score_filter', [[{}, {}]], {})).rejects.toThrow()
        })
    })

    describe('applyFilter', () => {
        it('should call POST /filters/{filterName}/apply with label-group-id query param', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: null })

            const instances = [{ type: 'single_label' }]
            await applyFilter('score_filter', 10, instances, { createCopy: false })

            expect(client.post).toHaveBeenCalledWith(
                '/filters/score_filter/apply',
                {
                    instances: instances,
                    options: { createCopy: false }
                },
                {
                    params: { 'label-group-id': 10 }
                }
            )
        })

        it('should return void (204 No Content)', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: null })

            const result = await applyFilter('score_filter', 5, [], {})

            expect(result).toBeUndefined()
        })

        it('should propagate 404 error when filter not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Filter not found' })
            )

            await expect(applyFilter('invalid', 1, [], {})).rejects.toThrow()
        })

        it('should propagate 400 error for validation errors', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Instance validation error' })
            )

            await expect(applyFilter('score_filter', 1, [{ bad: true }], {})).rejects.toThrow()
        })
    })
})
