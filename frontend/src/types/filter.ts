/* eslint-disable @typescript-eslint/no-explicit-any */
import { type Label } from './label'

// --- Base schemas ---

export interface InstanceBase {
    [key: string]: any
}

export interface ContextBase {
    [key: string]: any
}

// --- Concrete context types ---

export interface SentenceContext extends ContextBase {
    type : 'sentence'
    text : string
    labelStartRel : number
    labelEndRel : number
    label? : Label | null
    chapterContentId : string
}

export interface ParagraphContext extends ContextBase {
    type : 'paragraph'
    text : string
    labelStartRel : number
    labelEndRel : number
    label? : Label | null
    chapterContentId : string
}

// --- Concrete instance types ---

export interface SingleLabel extends InstanceBase {
    type : 'single_label'
    label : Label
    chapterContentId : string
}

// --- Request/Response types ---

export interface InstanceOptions {
    instances : any[]
    options : Record<string, any>
}

export interface InstanceContextOptions {
    instanceContexts : [any, any][]
    options : Record<string, any>
}

export interface SchemaInfo {
    instanceSchema? : Record<string, any>
    contextSchema? : Record<string, any>
    flagInstancesOptionsSchema? : Record<string, any>
    getContextsOptionsSchema? : Record<string, any>
    decideInstancesOptionsSchema? : Record<string, any>
    applyFilterOptionsSchema? : Record<string, any>
}
/* eslint-enable @typescript-eslint/no-explicit-any */
