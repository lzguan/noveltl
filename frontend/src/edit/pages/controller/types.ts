import type { AddLabelOp, CacheEntry, DeleteLabelOp, DetailHttpErrorResponse, Label, LabelData, LabelGroup, ModifyChapterContentResponse, Role, TextOp, UpdateLabelOp } from "@/client";
import type { ColorStyle, ProductStyle } from "@/components/labeled-text-lib/builtin/reducers";
import type { SegmentManager } from "@/components/labeled-text-lib/core/segmentManager";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";

export type MyStyle = ProductStyle<[
    ColorStyle, 
    { 
        visible: boolean, 
        mutable: boolean, 
        cursorStatus: "clicked" | "hovered" | "none" , 
        active: boolean 
    }
]>

export type LabelOp = AddLabelOp | DeleteLabelOp | UpdateLabelOp


/**
 * Event types that (might) affect the text/labels or the UI state of the editor, which need to be processed by the controller.
 */
export type UserEvent = { eventType : "textOp", op : TextOp } // text op 
| { eventType : "labelOp", op : LabelOp, labelGroupId : string } // label op
| { eventType : "addLabelGroup", labelGroupName : string } // add a new label group
| { eventType : "switchMode", mode : "edit" | "label" | "view" } // switch between text editing mode, label editing mode and view mode (no editing)
| { eventType : "switchLabelGroup", labelGroupId : string | null } // place focus on a specific label group
| { eventType : "hoverPos", pos : number | null } // hover on a specific position in text, or null to clear hover (only for ui purposes, does not affect the actual labels meaningfully)
| { eventType : "clickPos", pos : number | null } // click on a specific position in text, or null to clear click (only for ui purposes, does not affect the actual labels meaningfully)

export type Signal = null | { signalType : "changeLabelGroupId", oldId : string, newId : string }

export type RequestVariant = "addLabelGroup" | "textOp" | "labelOp" | "addLabelData"
export type RequestEvent = {
    callback : (requestKey : string) => Promise<Signal>
    handleCachedResult : (cachedResult : CacheEntry, requestKey : string) => { signal : Signal, status : "success", error : null } | { signal : null, status : "pending", error : null } | { signal : null, status : "failure", error : Error }
    reserveList : { id : ProvisionalId, kind : Kind, desiredState : IdStatus }[]
    variant : RequestVariant
}

export type KeyedRequestEvent = RequestEvent & { requestKey : string, retries: number }

export type ProvisionalLabelGroup = LabelGroup & { provisional: true }
export type ProvisionalLabelData = LabelData & { provisional: true }
export type ProvisionalLabel = Label & { provisional: true }


export type DataEntry = {
    labelGroup : ProvisionalLabelGroup
    labelData : ProvisionalLabelData
    labels : ProvisionalLabel[] // sorted by start position
    role : Role
    visible : boolean
}

/**
 * State transitions for id objects in the repository:
 * pending -> creating
 * creating -> clean
 * clean -> updating
 * clean -> idUpdating
 * clean -> deleting
 * clean -> locked
 * locked -> locked
 * locked -> clean
 * updating -> clean
 * idUpdating -> clean
 * deleting -> deleted
 * 
 * creating, updating, idUpdating, deleting states effectively lock this resource
 * locked state effectively makes this resource read-only, but can be reserved multiple times until all locks are released (do not use this state for writes)
 */

export type InFlightIdStatus = "creating" | "updating" | "idUpdating" | "deleting" | "locked"
export type GroundIdStatus = "pending" | "clean" | "deleted"

export type IdStatus = InFlightIdStatus | GroundIdStatus

export function entryStatus(status : InFlightIdStatus): GroundIdStatus {
    if (status === "creating") {
        return "pending"
    }
    return "clean"
}

export function exitStatus(status : InFlightIdStatus) : GroundIdStatus {
    if (status === "creating" || status === "updating" || status === "idUpdating" || status === "locked") {
        return "clean"
    }
    return "deleted"
}

export function isInFlight(status : IdStatus) : status is InFlightIdStatus {
    return status === "creating" || status === "updating" || status === "idUpdating" || status === "deleting" || status === "locked"
}

export type IdentifiableKind = "labelGroup" | "labelData" | "chapterContent"
export type ExistableKind = "label"
export type Kind = IdentifiableKind | ExistableKind

export type IdentifiableKindMap = { [K in IdentifiableKind] : Map<ProvisionalId, { serverId : ServerId | null, status : IdStatus, lockCount : number }> } 
export type ExistableKindMap = { [K in ExistableKind] : Map<ProvisionalId, { serverExists : ServerExists | null, status : IdStatus, lockCount : number }> }

export function isIdentifiableKind(kind : Kind) : kind is IdentifiableKind {
    return kind === "labelGroup" || kind === "labelData" || kind === "chapterContent"
}


export type ProvisionalId = string
export type ServerId = string
export type ServerExists = true

/**
 * Used for managing existence of ids, not state
 */
export interface IDRepository {
    /**
     * Create a new id and manage it in the repository. 
     */
    newId(kind : Kind) : ProvisionalId

    /**
     * Create a new id, bind it to the given server id, and manage it in the repository. 
     */
    newIdAndBindId(kind : IdentifiableKind, serverId : ServerId) : ProvisionalId
    newIdAndBindExists(kind : ExistableKind) : ProvisionalId

    /**
     * Get the server id corresponding to a provisional id. If server id has not been bound yet, return null. 
     */
    getServerId(kind : IdentifiableKind, provisionalId : ProvisionalId) : ServerId | null
    getServerExists(kind : ExistableKind, provisionalId : ProvisionalId) : ServerExists | null

    /**
     * Bind a provisional id to a server id, so that the controller can update the corresponding entry with the new server id when it receives the signal from the request event.
     */
    bindServerId(kind : IdentifiableKind, provisionalId : ProvisionalId, serverId : ServerId) : void
    bindServerExists(kind : ExistableKind, provisionalId : ProvisionalId) : void

    idObjState(kind : Kind, id : ProvisionalId) : IdStatus

    isReserveable(kind : Kind, id : ProvisionalId, desiredState : IdStatus) : boolean

    reserveIdObjState(kind : Kind, id : ProvisionalId, desiredState : IdStatus) : boolean

    releaseIdObjStateOnSuccess(kind : Kind, id : ProvisionalId) : void

    releaseIdObjStateOnFailure(kind : Kind, id : ProvisionalId) : void
}

export type DataManager = {

    addLabelGroup : (labelGroupName : string) => [ProvisionalId, RequestEvent[]]
    addLabel : (labelGroupId : string, labelDataId : string, startPos : number, endPos : number, word : string, entityGroup? : string, score? : number, dirty? : boolean) => ProvisionalId
    deleteLabel : (labelGroupId : string, labelDataId : string, startPos : number, endPos : number) => ProvisionalId
    updateLabel : (labelGroupId : string, labelDataId : string, startPos : number, endPos : number, newStartPos? : number | null, newEndPos? : number | null, newWord? : string | null,  entityGroup? : string, score? : number, dirty? : boolean) => ProvisionalId
    flushLabelOps : () => RequestEvent[]
    insertTextAt : (pos : number, text : string) => void
    deleteTextAt : (startPos : number, endPos : number) => void
    flushTextOps : () => RequestEvent[]

    handleSignal : (signal : Signal) => void

    getEntries : () => readonly DataEntry[]
}


export class TimeoutError extends Error {
    constructor(message : string) {
        super(message)
        this.name = "TimeoutError"
    }
}

export class CacheConflictError extends Error {
    requestKey : string
    constructor(message : string, requestKey : string) {
        super(message)
        this.name = "CacheConflictError"
        this.requestKey = requestKey
    }
}

export class NoCacheEntryError extends Error {
    requestKey : string
    constructor(message : string, requestKey : string) {
        super(message)
        this.name = "NoCacheEntryError"
        this.requestKey = requestKey
    }
}

export class ConnectionError extends Error {
    orig : unknown
    constructor(message : string, err : unknown) {
        super(message)
        this.name = "ConnectionError"
        this.orig = err
    }
}

export class FatalError extends Error {
    orig? : unknown
    constructor(message : string, orig? : unknown) {
        super(message)
        this.name = "FatalError"
        if (orig) {
            this.orig = orig
        }
    }
}

export type RequestManager = {
    isQueueEmpty : () => boolean
    enqueueRequest : (request : RequestEvent) => void

    handleSignal : (signal : Signal) => void

    onUserEvent : (event : UserEvent) => void
    send : () => Promise<void>
    start : () => Promise<void>

    attachControllerSignalHandler : (handler : (signal : Signal) => void) => void
}


export interface Controller {
    handleEvent : (event : UserEvent) => void
    uiManager : SegmentManager<MyStyle, StyledLabel<MyStyle>>
    handleSignal : (signal : Signal) => void
}


export type Validator<T> = (value: unknown) => value is T

type Shape = { [key: string]: Validator<unknown> }

const isObject = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null

const isString: Validator<string> = (value): value is string => typeof value === "string"
const isNumber: Validator<number> = (value): value is number => typeof value === "number" && Number.isFinite(value)
const isBoolean: Validator<boolean> = (value): value is boolean => typeof value === "boolean"

const isRecordOf = <T>(valueValidator: Validator<T>): Validator<Record<string, T>> =>
    (value): value is Record<string, T> =>
        isObject(value) && Object.values(value).every(valueValidator)

const hasShape = <T extends Shape>(
    shape: T,
): Validator<{ [K in keyof T]: T[K] extends Validator<infer U> ? U : never }> =>
    (value): value is { [K in keyof T]: T[K] extends Validator<infer U> ? U : never } =>
        isObject(value) && Object.entries(shape).every(([key, validator]) => validator(value[key]))

export function validateData<T>(schema: Validator<T>, data: unknown): T {
    if (!schema(data)) {
        throw new TypeError("Cached response did not match expected schema")
    }
    return data
}

export const isLabelGroup = hasShape({
    labelGroupId: isString,
    labelGroupName: isString,
    novelId: isString,
}) as Validator<LabelGroup>

export const isLabelData = hasShape({
    labelDataId: isString,
    labelGroupId: isString,
    chapterContentId: isString,
}) as Validator<LabelData>

export const isModifyChapterContentResponse = hasShape({
    chapterContentVersion: isNumber,
    chapterContentId: isString,
    labelDataIdMap: isRecordOf(isString),
}) as Validator<ModifyChapterContentResponse>

export const isDetailHttpErrorResponse = hasShape({
    detail: isString,
}) as Validator<DetailHttpErrorResponse>

export const _isRequestConflictErrorResponse = hasShape({
    detail: isString,
    cacheConflict: isBoolean
}) as Validator<{ detail: string, cacheConflict: boolean }>

export const isRequestConflictErrorResponse = hasShape({
    detail: _isRequestConflictErrorResponse
}) as Validator<{ detail: { detail: string, cacheConflict: boolean } }>
