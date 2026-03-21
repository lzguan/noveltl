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
    revisionId : number
}

export interface CreateLabelData {
    revisionId : number
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
