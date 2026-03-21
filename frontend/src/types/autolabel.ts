import { type Label } from './label'

export type AutoLabelProgress = 'pending' | 'processing' | 'done' | 'failed'

export type SepPriority = 'high' | 'med' | 'low'

export interface AutoLabel {
    autoLabelId : number
    autoLabelData : Label[] | null
    autoLabelModelName : string
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    autoLabelModelParams : Record<string, any>
    autoLabelStatus : AutoLabelProgress
    autoLabelMessage : string | null
    revisionId : number
    autoLabelLastJobId : string
}

export type AutoLabelMeta = Omit<AutoLabel, 'autoLabelData'>

export interface CreateAutoLabels {
    novelId : number
    autoLabelModelName : string
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    autoLabelModelParams : Record<string, any>
    chapterIds? : number[] | null
    revisionIds? : number[] | null
    start? : number | null
    end? : number | null
    isPrimary? : boolean | null
    isPublic? : boolean | null
}
