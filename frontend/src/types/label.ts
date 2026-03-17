// --- Label Group ---

export interface LabelGroup {
    labelGroupId : number
    labelGroupName : string
    novelId : number
}

export interface CreateLabelGroup {
    labelGroupName : string
    novelId : number
}

export interface UpdateLabelGroup {
    labelGroupName : string
}

// --- Label ---

export interface Label {
    labelEntityGroup : string | null
    labelScore : number
    labelWord : string
    labelStart : number
    labelEnd : number
    labelDirty : boolean
}

// --- Label Data ---

export interface LabelData {
    labelDataId : number
    labelGroupId : number
    rawChapterRevisionId : number
}

export interface CreateLabelData {
    rawChapterRevisionId : number
}

// --- Label Operations ---

export interface AddLabelOp {
    op : 'add'
    startPos : number
    endPos : number
    word : string
    dirty? : boolean
    entityGroup? : string | null
    score? : number
}

export interface DeleteLabelOp {
    op : 'delete'
    startPos : number
    endPos : number
    word : string
}

export interface UpdateLabelOp {
    op : 'update'
    startPos : number
    endPos : number
    word : string
    newStartPos? : number | null
    newEndPos? : number | null
    newWord? : string | null
    dirty? : boolean | null
    entityGroup? : string | null
    score? : number | null
}

export type LabelOp = AddLabelOp | DeleteLabelOp | UpdateLabelOp

// --- Stream / Status ---

export interface UpdateLabelDataStream {
    ops : LabelOp[]
}

export interface UpdateLabelDataStreamResponse {
    status : 'success' | 'fail'
    detail? : string | null
}

// --- Auto-Label Import ---

export interface CreateLabelDataByAutoLabel {
    modelName : string
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    modelParams : Record<string, any>
    rawChapterIds? : number[] | null
    rawChapterRevisionIds? : number[] | null
    start? : number | null
    end? : number | null
}

export interface CreateLabelDataByAutoLabelStatus {
    success : number[]
    errors : [number, string][]
}
