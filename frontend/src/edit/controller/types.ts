import type { AddLabelOp, CacheEntry, DeleteLabelOp, DetailHttpErrorResponse, Label, LabelData, LabelGroup, ModifyChapterContentResponse, Role, TextOp, UpdateLabelOp } from "@/client";
import type { Color } from "@/components/labeled-text-lib/builtin/colors";
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
| { eventType : "loadGroup", labelGroupId : string } // load a specific label group
| { eventType: "toggleVisibility", labelGroupId: string, visible: boolean } // toggle visibility of a specific label group

type GroupLoadedSignal = { type: "groupLoaded", labelGroupId : string, getLabels : () => ProvisionalLabel[], mutable : boolean }
type ClearLabelsSignal = { type : "clearLabels", labelIds : ProvisionalId[] }
type DetachedIdsSignal = { type : "detachedIds", detachedIds : { id: ProvisionalId, kind: Kind }[] }

export type Signal = null
| GroupLoadedSignal
| ClearLabelsSignal
| DetachedIdsSignal

type DecoratedGroupLoadedSignal = GroupLoadedSignal & { visible: boolean, color: Color }

declare const DecoratedSignalTag : unique symbol

type _DecoratedSignal = DecoratedGroupLoadedSignal | ClearLabelsSignal | DetachedIdsSignal

export type DecoratedSignal = _DecoratedSignal & { [DecoratedSignalTag] : typeof DecoratedSignalTag }

export function makeDecoratedSignal(signal : _DecoratedSignal) : DecoratedSignal {
    return signal as DecoratedSignal
}

type CachedResultOutput = { signal : Signal, status : "success", error : null } | { signal : null, status : "pending", error : null } | { signal : null, status : "failure", error : Error }

export type RequestVariant = "addLabelGroup" | "textOp" | "labelOp" | "addLabelData" | "reloadGroup"

export type Reservation = {
    kind : Kind,
    id : ProvisionalId,
    desiredState : InFlightIdStatus
}

export type StaticReservationRequest = {
    reserveList : Reservation[]
    skip? : () => boolean
    wait? : never
}


declare const IDCTag : unique symbol 

type IdempotentCallable<T> = {
    call : () => T
    readonly [IDCTag] : typeof IDCTag
}

export function makeIdempotent<T>(fn : () => T) : IdempotentCallable<T> {
    let called = false
    let result : T
    return {
        call: () => {
            if (!called) {
                result = fn()
                called = true
            }
            return result!
        },
    } as IdempotentCallable<T>
}

export type LazyReservationRequest = {
    reserveList : IdempotentCallable<Reservation[]>
    /**
     * If provided, skip this request if this function returns true provided that wait() returns false.
     */
    skip? : () => boolean
    /**
     * Wait to send this request until this function returns false. If not provided, the request manager will not delay this request.
     */
    wait : () => boolean
}


export type BaseRequestEvent = {
    callback : (requestKey : string) => Promise<Signal>
    reservationRequest : StaticReservationRequest | LazyReservationRequest
    variant: RequestVariant,
    onFailure?: () => void, // optional handler that will be called if the request fails after all retries, with the error that caused the failure
    onFatalError?: (err : Error) => void, // optional handler that will be called if the request encounters a fatal error
    retries: number,
}
export type NoCachedRequestEvent = BaseRequestEvent & { handleCachedResult?: never }

export type CachedRequestEvent = BaseRequestEvent & { 
    handleCachedResult : (cachedResult : CacheEntry, requestKey : string) => CachedResultOutput // if not provided, the callback should never throw a CacheConflictError, and the request manager will not attempt to handle cache results for this request
}

export type RequestEvent = CachedRequestEvent | NoCachedRequestEvent

export type NoCachedKeyedRequestEvent = NoCachedRequestEvent & { requestKey : string }
export type CachedKeyedRequestEvent = CachedRequestEvent & { requestKey : string }

export type KeyedRequestEvent = NoCachedKeyedRequestEvent | CachedKeyedRequestEvent

export type ProvisionalLabelGroup = LabelGroup & { provisional: true }
export type ProvisionalLabelData = LabelData & { provisional: true }
export type ProvisionalLabel = Label & { provisional: true }

export type LoadingStatus = "notLoaded" | "loading" | "loaded" | "loadError"

export type DataEntry = {
    labelGroup : ProvisionalLabelGroup
    labelData : ProvisionalLabelData
    labels : ProvisionalLabel[] // sorted by start position
    role : Role

    loadingStatus : LoadingStatus
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
 * 
 * slightly outdated
 */

export type InFlightIdStatus = "creating" | "updating" | "idUpdating" | "deleting" | "locked" | "detaching" | "loading" | "killing"
export type GroundIdStatus = "pending" | "clean" | "deleted" | "detached" | "killed"

export type IdStatus = InFlightIdStatus | GroundIdStatus

export function entryStatus(status : InFlightIdStatus): GroundIdStatus {
    if (status === "creating" || status === "loading" || status === "killing") {
        return "pending"
    }
    return "clean"
}

export function exitStatus(status : InFlightIdStatus) : GroundIdStatus {
    if (status === "creating" || status === "updating" || status === "idUpdating" || status === "locked" || status === "loading") {
        return "clean"
    }
    else if (status === "detaching") {
        return "detached"
    }
    else if (status === "killing") {
        return "killed"
    }
    return "deleted"
}

export function isInFlight(status : IdStatus) : status is InFlightIdStatus {
    return status === "creating" || status === "updating" || status === "idUpdating" || status === "deleting" || status === "locked" || status === "detaching" || status === "loading" || status === "killing"
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

    isReserveable(kind : Kind, id : ProvisionalId, desiredState : InFlightIdStatus) : boolean

    reserveIdObjState(kind : Kind, id : ProvisionalId, desiredState : InFlightIdStatus) : boolean

    releaseIdObjStateOnSuccess(kind : Kind, id : ProvisionalId) : void

    releaseIdObjStateOnFailure(kind : Kind, id : ProvisionalId) : void

    gc(): void
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


    handleSignal : (signal : DecoratedSignal) => void

    reloadGroup(labelGroupId : string) : RequestEvent[]

    getForGroup: {
        labelDataId: (labelGroupId : string) => string
        role: (labelGroupId : string) => Role
        labels: (labelGroupId : string) => readonly Label[]
        loadingStatus: (labelGroupId : string) => LoadingStatus
        name: (labelGroupId : string) => string
    }
    getGroups : () => readonly LabelGroup[]

    /**
     * Attach a label group sync handler
     */
    attachLabelGroupSyncHandler : (handler : () => void) => void
}

export type UIManager = {
    segmentManager : SegmentManager<MyStyle, StyledLabel<MyStyle>>
    handleSignal : (signal : DecoratedSignal) => void
    toggleVisibility : (labelIds: ProvisionalId[], visible: boolean) => void
    toggleClickStatus : (labelIds: ProvisionalId[], clickStatus: "clicked" | "none") => void
    toggleHoverStatus : (labelIds: ProvisionalId[], hoverStatus: "hovered" | "none") => void
    toggleActiveStatus : (labelIds: ProvisionalId[], activeStatus: boolean) => void
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

    handleSignal : (signal : DecoratedSignal) => void

    onUserEvent : (event : UserEvent) => void
    send : () => Promise<null | number> // returns null if no delay is needed or the delay until the next retry if a request was sent and needs to be retried
    start : () => Promise<void>

    /**
     * Attach a handler for signals that are received by the request manager when processing request events.
     */
    attachControllerSignalHandler : (handler : (signal : Signal) => void) => void
}


export type LabelGroupView = {
    labelGroupId : ProvisionalId,
    labelGroupName : string,
    role : Role,
    loadingStatus : LoadingStatus
    visible : boolean
    color : Color
}

export interface Controller {
    handleEvent : (event : UserEvent) => void
    uiManager : UIManager
    handleSignal : (signal : Signal) => void // not decorated

    labelGroupViews : LabelGroupView[]
    activeLabelGroupId : ProvisionalId | null
}

export type Runtime = {
    idRepo : IDRepository
    requestManager : RequestManager
    provisionalChapterContentId : string
    entries : DataEntry[]
    dataManager : DataManager
    colorMapping : Map<ProvisionalId, Color>
    visibilityMapping : Map<ProvisionalId, boolean>
    uiManager : UIManager
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

export const isLabel = hasShape({
    labelId: isString,
    labelDataId: isString,
    labelStart : isNumber,
    labelEnd : isNumber,
    labelWord : isString,
    labelEntityGroup: (val) => isString(val) || val === null,
    labelScore: isNumber,
    labelDirty: isBoolean,
}) as Validator<Label>

export const isArrayOf = <T>(itemValidator: Validator<T>): Validator<T[]> =>
    (value): value is T[] =>
        Array.isArray(value) && value.every(itemValidator)

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
