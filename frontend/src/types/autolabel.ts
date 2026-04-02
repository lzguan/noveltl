import { type Label } from './label'

export type AutoLabelProgress = 'pending' | 'processing' | 'done' | 'failed'

export type SepPriority = 'high' | 'med' | 'low'

export interface AutoLabel {
    autoLabelId : string
    autoLabelData : Label[] | null
    autoLabelModelName : string
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    autoLabelModelParams : Record<string, any>
    autoLabelStatus : AutoLabelProgress
    autoLabelMessage : string | null
    revisionTextId : string
    autoLabelLastJobId : string
}

export type AutoLabelMeta = Omit<AutoLabel, 'autoLabelData'>

export interface CreateAutoLabels {
    novelId : string
    autoLabelModelName : string
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    autoLabelModelParams : Record<string, any>
    chapterIds? : string[] | null
    revisionIds? : string[] | null
    start? : number | null
    end? : number | null
    isPrimary? : boolean | null
    isPublic? : boolean | null
}
