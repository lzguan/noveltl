import client from "./client";
import {
    type LabelGroup,
    type CreateLabelGroup,
    type UpdateLabelGroup,
    type LabelData,
    type CreateLabelData,
    type Label,
    type LabelOp,
    type UpdateLabelDataStream
} from "../types/label";

// --- Response mappers (API snake_case → frontend camelCase) ---

/* eslint-disable @typescript-eslint/no-explicit-any */

const mapLabelGroup = (data: any): LabelGroup => ({
    labelGroupId: data.label_group_id,
    labelGroupName: data.label_group_name,
    novelId: data.novel_id,
})

const mapLabelData = (data: any): LabelData => ({
    labelDataId: data.label_data_id,
    labelGroupId: data.label_group_id,
    rawChapterRevisionId: data.raw_chapter_revision_id,
})

const mapLabel = (data: any): Label => ({
    labelEntityGroup: data.label_entity_group,
    labelScore: data.label_score,
    labelWord: data.label_word,
    labelStart: data.label_start,
    labelEnd: data.label_end,
    labelDirty: data.label_dirty,
})

/* eslint-enable @typescript-eslint/no-explicit-any */

// --- Request mappers (frontend camelCase → API snake_case) ---

const mapCreateLabelGroupRequest = (data: CreateLabelGroup) => ({
    label_group_name: data.labelGroupName,
    novel_id: data.novelId,
})

const mapUpdateLabelGroupRequest = (data: UpdateLabelGroup) => ({
    label_group_name: data.labelGroupName,
})

const mapCreateLabelDataRequest = (data: CreateLabelData) => ({
    raw_chapter_revision_id: data.rawChapterRevisionId,
})

const mapLabelOp = (op: LabelOp) => {
    const base = {
        op: op.op,
        start_pos: op.startPos,
        end_pos: op.endPos,
        word: op.word,
    }
    
    if (op.op === 'add') {
        return {
            ...base,
            dirty: op.dirty,
            entity_group: op.entityGroup,
            score: op.score,
        }
    } else if (op.op === 'update') {
        return {
            ...base,
            new_start_pos: op.newStartPos,
            new_end_pos: op.newEndPos,
            new_word: op.newWord,
            dirty: op.dirty,
            entity_group: op.entityGroup,
            score: op.score,
        }
    }
    
    return base
}

const mapUpdateLabelDataStreamRequest = (data: UpdateLabelDataStream) => ({
    ops: data.ops.map(mapLabelOp),
})

// --- API functions ---

export const getLabelGroupsByNovel = async (novelId : number) : Promise<LabelGroup[]> => {
    const result = await client.get(`/label-groups`, {
        params: {
            "novel-id": novelId
        }
    })
    return result.data.map(mapLabelGroup)
}

export const createLabelGroup = async (request : CreateLabelGroup) : Promise<LabelGroup> => {
    const result = await client.post('/label-groups', mapCreateLabelGroupRequest(request))
    return mapLabelGroup(result.data)
}

export const getLabelGroupById = async (labelGroupId : number) : Promise<LabelGroup> => {
    const result = await client.get(`/label-groups/${labelGroupId}`)
    return mapLabelGroup(result.data)
}

export const updateLabelGroup = async (labelGroupId : number, request : UpdateLabelGroup) : Promise<LabelGroup> => {
    const result = await client.patch(`/label-groups/${labelGroupId}`, mapUpdateLabelGroupRequest(request))
    return mapLabelGroup(result.data)
}

export const getLabelDatas = async (
    labelGroupId : number,
    start? : number,
    end? : number
) : Promise<LabelData[]> => {
    const result = await client.get('/label-datas', {
        params: {
            'label-group-id': labelGroupId,
            start,
            end
        }
    })
    return result.data.map(mapLabelData)
}

export const getLabelDataById = async (labelDataId : number) : Promise<LabelData> => {
    const result = await client.get(`/label-datas/${labelDataId}`)
    return mapLabelData(result.data)
}

export const getLabelsByLabelData = async (labelDataId : number) : Promise<Label[]> => {
    const result = await client.get(`/label-datas/${labelDataId}/labels`)
    return result.data.map(mapLabel)
}

export const createLabelDataForGroup = async (
    labelGroupId : number,
    request : CreateLabelData
) : Promise<LabelData> => {
    const result = await client.post(`/label-groups/${labelGroupId}/label-datas`, mapCreateLabelDataRequest(request))
    return mapLabelData(result.data)
}

export const updateLabelDataStream = async (
    labelDataId : number,
    request : UpdateLabelDataStream
) : Promise<void> => {
    await client.patch(`/label-datas/${labelDataId}`, mapUpdateLabelDataStreamRequest(request))
}
