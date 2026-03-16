import client from './client'
import {
    type AutoLabel,
    type AutoLabelMeta,
    type CreateAutoLabels
} from '../types/autolabel'

// --- Response mappers (API snake_case → frontend camelCase) ---

/* eslint-disable @typescript-eslint/no-explicit-any */

const mapLabel = (data: any) => ({
    labelEntityGroup: data.label_entity_group,
    labelScore: data.label_score,
    labelWord: data.label_word,
    labelStart: data.label_start,
    labelEnd: data.label_end,
    labelDirty: data.label_dirty,
})

const mapAutoLabel = (data: any): AutoLabel => ({
    autoLabelId: data.auto_label_id,
    autoLabelData: data.auto_label_data ? data.auto_label_data.map(mapLabel) : null,
    autoLabelModelName: data.auto_label_model_name,
    autoLabelModelParams: data.auto_label_model_params,
    autoLabelStatus: data.auto_label_status,
    autoLabelMessage: data.auto_label_message,
    rawChapterRevisionId: data.raw_chapter_revision_id,
    autoLabelLastJobId: data.auto_label_last_job_id,
})

const mapAutoLabelMeta = (data: any): AutoLabelMeta => ({
    autoLabelId: data.auto_label_id,
    autoLabelModelName: data.auto_label_model_name,
    autoLabelModelParams: data.auto_label_model_params,
    autoLabelStatus: data.auto_label_status,
    autoLabelMessage: data.auto_label_message,
    rawChapterRevisionId: data.raw_chapter_revision_id,
    autoLabelLastJobId: data.auto_label_last_job_id,
})

/* eslint-enable @typescript-eslint/no-explicit-any */

// --- Request mappers (frontend camelCase → API snake_case) ---

const mapCreateAutoLabelsRequest = (data: CreateAutoLabels) => ({
    novel_id: data.novelId,
    auto_label_model_name: data.autoLabelModelName,
    auto_label_model_params: data.autoLabelModelParams,
    raw_chapter_ids: data.rawChapterIds,
    raw_chapter_revision_ids: data.rawChapterRevisionIds,
    start: data.start,
    end: data.end,
    is_primary: data.isPrimary,
    is_public: data.isPublic,
})

// --- API functions ---

export const getAutoLabelById = async (autoLabelId: number): Promise<AutoLabel> => {
    const result = await client.get(`/auto-labels/${autoLabelId}`)
    return mapAutoLabel(result.data)
}

export const getAutoLabels = async (
    novelId: number,
    rawChapterIds?: number[] | null,
    rawChapterRevisionIds?: number[] | null,
    start?: number | null,
    end?: number | null,
    modelNames?: string[] | null
): Promise<Record<number, AutoLabelMeta>> => {
    const result = await client.get('/auto-labels', {
        params: {
            'novel-id': novelId,
            'raw-chapter-ids': rawChapterIds,
            'raw-chapter-revision-ids': rawChapterRevisionIds,
            start,
            end,
            'model-names': modelNames,
        }
    })
    
    // Map the dictionary values
    const mapped: Record<number, AutoLabelMeta> = {}
    for (const [key, value] of Object.entries(result.data)) {
        mapped[Number(key)] = mapAutoLabelMeta(value)
    }
    return mapped
}

export const createAutoLabels = async (request: CreateAutoLabels): Promise<AutoLabelMeta[]> => {
    const result = await client.post('/auto-labels', mapCreateAutoLabelsRequest(request))
    return result.data.map(mapAutoLabelMeta)
}
