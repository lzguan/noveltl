import client from './client'
import { type SchemaInfo } from '../types/filter'

// --- API functions ---

/* eslint-disable @typescript-eslint/no-explicit-any */
export const getFilterSchemas = async (): Promise<Record<string, SchemaInfo>> => {
    const result = await client.get('/filters/schemas')
    return result.data
}

export const flagInstances = async (
    filterName: string,
    options: Record<string, any>
): Promise<any[]> => {
    const result = await client.post(`/filters/${filterName}/flag-instances`, options)
    return result.data
}

export const getContexts = async (
    filterName: string,
    instances: any[],
    options: Record<string, any>
): Promise<any[]> => {
    const result = await client.post(`/filters/${filterName}/get-contexts`, {
        instances,
        options
    })
    return result.data
}

export const decideInstances = async (
    filterName: string,
    instanceContexts: [any, any][],
    options: Record<string, any>
): Promise<boolean[]> => {
    const result = await client.post(`/filters/${filterName}/decide-instances`, {
        instance_contexts: instanceContexts,
        options
    })
    return result.data
}

export const applyFilter = async (
    filterName: string,
    labelGroupId: string,
    instances: any[],
    options: Record<string, any>
): Promise<void> => {
    await client.post(`/filters/${filterName}/apply`, {
        instances,
        options
    }, {
        params: {
            'label-group-id': labelGroupId
        }
    })
}
/* eslint-enable @typescript-eslint/no-explicit-any */
