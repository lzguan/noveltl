// --- Label Group ---

export interface LabelGroup {
    labelGroupId : string
    labelGroupName : string
    novelId : string
}

export interface CreateLabelGroup {
    labelGroupName : string
    novelId : string
}

export interface UpdateLabelGroup {
    labelGroupName : string
}

// --- Label ---

export interface Label {
    labelDataId? : string
    labelEntityGroup : string | null
    labelScore : number
    labelWord : string
    labelStart : number
    labelEnd : number
    labelDirty : boolean
}

// --- Label Data ---

export interface LabelData {
    labelDataId : string
    labelGroupId : string
    chapterContentId : string
}

export interface CreateLabelData {
    chapterContentId : string
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
    chapterIds? : string[] | null
    start? : number | null
    end? : number | null
}

export interface CreateLabelDataByAutoLabelStatus {
    success : [string, string][]
    errors : [string, string, string][]
}
