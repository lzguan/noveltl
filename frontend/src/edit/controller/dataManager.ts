import type { Chapter, Novel, TextOp } from "@/client"
import { type DataEntry, type LabelOp, type DataManager, type IDRepository, type ProvisionalId, type RequestEvent, type ProvisionalLabelGroup, type Kind, ConnectionError, CacheConflictError, FatalError, type InFlightIdStatus, type ProvisionalLabel, isInFlight, makeIdempotent, type Reservation, type DecoratedSignal } from "./types"
import { createLabelDataLabelGroupsLabelGroupIdLabelDatasPost, createLabelGroupLabelGroupsPost, readLabelContributorsLabelGroupsLabelGroupIdContributorsGet, readLabelDatasByGroupChaptersLabelDatasGet, readLabelGroupLabelGroupsLabelGroupIdGet, readLabelsByLabelDataLabelDatasLabelDataIdLabelsGet, updateChapterContentChaptersChapterIdContentPatch, updateLabelDataStreamLabelDatasLabelDataIdPatch } from "@/client"
import { isDetailHttpErrorResponse, isLabelData, isLabelGroup, isRequestConflictErrorResponse, validateData, isModifyChapterContentResponse } from "./types"
import { createLogger } from "@/lib/logging";

const logger = createLogger("DataManager")

/**
 * The data manager is built on top of the ID repository and is responsible for managing the state of the data entries and providing functions to mutate the data. Below is a description of the interfaces exposed by the data manager.
 * 
 * The internal state of the data manager consists of a set of data objects holding the UI state of the editor. Specifically, it contains the following components:
 * - A chapter content id
 * - The current chapter text
 * - A list of data entries, where each entry corresponds to a label group, a label data, and the labels associated.
 * These data objects should hold snapshots of an optimistic view of the server state. As such, no element here is nullable.
 * 
 * The data manager is also responsible for ensuring that any operations performed keep the internal state consistent. Namely, no two labels from the same label data should overlap.
 * 
 * The data manager also contains a queue of pending label operations and a queue of pending text operations. Broadly speaking, there are two categories of interfaces exposed by the data manager:
 * 1. Interaction interfaces - functions called by the controller upon receiving user interactions to mutate internal state of data manager + add the operations performed to a queue.
 * 2. Flush interfaces - functions called by the controller to flush pending operations to the server. These functions generate lists of request events to be sent to the server and flush the corresponding internal queues. The controller is responsible for calling the flush interfaces at the appropriate times. 
 * 
 * The controller is responsible for calling flush interfaces in the correct order. Namely, a queue of pending label operations performed before a text operation should be flushed before the text operation, and a queue of pending label operations performed after a text operation should be flushed after the text operation. The data manager does not enforce this behaviour.
 * 
 * There is also a handleSignal interface which is called by the controller when a signal is received from the server. Not supported yet but may be in the future if necessary.
 * 
 * Some functions satisfy both the conditions for interaction interfaces and flush interfaces (namely addLabelGroup). These functions will perform the actions for interaction and then return the result of flushing without adding anything to an internal queue. 
 * 
 * A request event consists of the following components:
 * - variant: a string representing the type of the request event. 
 * - reserveList: a list of provisional ids along with the desired revervation status for each of the ids. The request manager uses this list to reserve the corresponding ids in the ID repository. The responsibility of reserving the ids does not fall on the data manager/generated request events.
 * - callback: an async function that calls the corresponding API endpoint, handles errors, and binds the correct server ids to the provisional ids in the ID repository. 
 * - handleCachedResult: a function that handles a cached result returned by the controller for a previously unresponsive sent request. This performs the same sort of id bidning as the callback function but for cached results but does not handle API calls.
 * 
 * In terms of error handling, the callback function is responsible for catching any errors and throwing the following typed error categories:
 * - Connection errors: errors where we fail to receive a response from the server. The callback function must throw a ConnectionError.
 * - Cache errors: errors where we receive a cache conflict response from the server. The callback function must throw a CacheConflictError.
 * - Fatal errors: errors where we receive a response from the server but it indicates some failure. The callback function must throw a FatalError.
 * 
 * A cached result response follows the following data model:
 * - status: a status string which can be "success", "failure", or "pending". "success" indicates the corresponding request completed successfully. "failure" indicates the corresponding request failed. "pending" indicates the corresponding request is still pending and we do not have any new information on its status.
 * - status_code: the HTTP status code returned by the server for the corresponding request. This field is only relevant when status is "success" or "failure". For "pending" requests, this field is null.
 * - response: if status is "success", this field contains the response returned by the server for the corresponding request. If status is "failure" or "pending", this field is null.
 * - error: if status is "failure", this field contains the error returned by the server for the corresponding request. If status is "success" or "pending", this field is null.
 * 
 * The handleCachedResult function in any request event should bind the correct server ids to the provisional ids in the ID repository. The request manager is responsible for passing the server response cached result to the handleCachedResult function.
 */
export function buildDataManager(ents : DataEntry[], idRepo : IDRepository, novel : Novel, chapter : Chapter, userId : string, initialChapterContentId : ProvisionalId, initialText : string) : DataManager {
    let entries : DataEntry[] = ents
    let text : string = initialText
    let labelGroupSyncHandler : (() => void) = () => {}

    const chapterContentId : ProvisionalId = initialChapterContentId
    let labelOpQueue : Map<ProvisionalId, { labelId : ProvisionalId, op : LabelOp }[]> = new Map()
    let textOpQueue : { op : TextOp, labelDataIds : ProvisionalId[], labelIds : ProvisionalId[] }[] = []

    const ensureNoPendingTextOps = () => {
        if (textOpQueue.length > 0) {
            throw new Error("Cannot mutate labels while text operations are pending flush.")
        }
    }

    const ensureNoPendingLabelOps = () => {
        const hasPendingLabelOps = Array.from(labelOpQueue.values()).some((ops) => ops.length > 0)
        if (hasPendingLabelOps) {
            throw new Error("Cannot mutate text while label operations are pending flush.")
        }
    }

    const queueLabelOp = (labelGroupId : ProvisionalId, labelId : ProvisionalId, op : LabelOp) => {
        if (!labelOpQueue.has(labelGroupId)) {
            labelOpQueue.set(labelGroupId, [])
        }
        labelOpQueue.get(labelGroupId)!.push({ labelId, op })
    }

    const getMatchingLabelIndex = (entry : DataEntry, startPos : number, endPos : number) => {
        return entry.labels.findIndex((label) => label.labelStart === startPos && label.labelEnd === endPos)
    }

    const addLabelGroup = (labelGroupName : string) : [ProvisionalId, RequestEvent[]] => {
        const provisionalGroupId = idRepo.newId("labelGroup")
        const provisionalDataId = idRepo.newId("labelData")
        const newLabelGroup : ProvisionalLabelGroup = {
            labelGroupId: provisionalGroupId,
            labelGroupName: labelGroupName,
            novelId: novel.novelId,
            provisional: true
        }
        const newEntries = [...entries]
        const contentIdSnapshot = chapterContentId
        newEntries.unshift({
            labelGroup: newLabelGroup,
            labelData: { labelDataId: provisionalDataId, labelGroupId: provisionalGroupId, chapterContentId: contentIdSnapshot, provisional: true },
            labels: [],
            role: "owner",
            loadingStatus: "notLoaded"
        })
        entries = newEntries
        labelGroupSyncHandler()
        let skipRemaining = false

        const cleanupAddLabelGroupFailure = () => {
            const entry = entries.find((candidate) => candidate.labelGroup.labelGroupId === provisionalGroupId)
            if (entry) {
                entry.loadingStatus = "loadError"
            }
            skipRemaining = true
            if (idRepo.isReserveable("labelData", provisionalDataId, "killing")) {
                idRepo.reserveIdObjState("labelData", provisionalDataId, "killing")
                idRepo.releaseIdObjStateOnSuccess("labelData", provisionalDataId)
            }
            else if (idRepo.isReserveable("labelData", provisionalDataId, "detaching")) {
                idRepo.reserveIdObjState("labelData", provisionalDataId, "detaching")
                idRepo.releaseIdObjStateOnSuccess("labelData", provisionalDataId)
            }
            labelGroupSyncHandler()
        }

        return [provisionalGroupId, [
            {
                variant: "addLabelGroup",
                retries: 3,
                callback: async (requestKey) => {
                    let resp
                    try {
                        resp = await createLabelGroupLabelGroupsPost({ 
                            body: {
                                novelId: novel.novelId,
                                labelGroupName: labelGroupName,
                            },
                            query: {
                                requestKey: requestKey,
                            }
                        })
                    } catch (err) {
                        logger.error("Failed to create label group", { error: err, requestKey })
                        throw new ConnectionError("Failed to create label group", err)
                    }
                    if (!resp.data) {
                        if (isRequestConflictErrorResponse(resp.error) && resp.error.detail.cacheConflict) {
                            throw new CacheConflictError("Request key conflict while creating label group", requestKey)
                        } else if (isDetailHttpErrorResponse(resp.error)) {
                            throw new FatalError(`Failed to create label group: ${resp.error.detail}`, resp.error)
                        }
                        throw new FatalError("Failed to create label group", resp.error)
                    }
                    idRepo.bindServerId("labelGroup", provisionalGroupId, resp.data.labelGroupId)
                    return null
                },
                handleCachedResult: (cachedResult, requestKey) => {
                    if (cachedResult.status === "success") {
                        const validated = validateData(isLabelGroup, cachedResult.response)
                        idRepo.bindServerId("labelGroup", provisionalGroupId, validated.labelGroupId)
                        return { status: cachedResult.status, signal: null, error : null }
                    }
                    else if (cachedResult.status === "pending") {
                        return { status: cachedResult.status, signal: null, error : null }
                    }
                    else {
                        if (cachedResult.error?.cacheConflict) {
                            return { status: cachedResult.status, signal: null, error : new CacheConflictError("Request key conflict while creating label group", requestKey) }
                        }
                        
                    }
                    return { status: cachedResult.status, signal: null, error : new FatalError("Failed to create label group", cachedResult.error instanceof Error ? cachedResult.error : new Error(JSON.stringify(cachedResult.error))) }
                },
                reservationRequest: {
                    reserveList: [ { id : provisionalGroupId, kind: "labelGroup", desiredState: "creating" } ],
                    skip: () => skipRemaining,
                },
                
                onFailure: cleanupAddLabelGroupFailure,
                onFatalError: cleanupAddLabelGroupFailure,
            },
            {
                variant: "addLabelGroup",
                retries: 3,
                callback: async (requestKey) => {
                    let resp
                    try {
                        resp = await createLabelDataLabelGroupsLabelGroupIdLabelDatasPost({
                            body: {
                                chapterContentId: idRepo.getServerId("chapterContent", contentIdSnapshot)!,
                            },
                            path: {
                                labelGroupId: idRepo.getServerId("labelGroup", provisionalGroupId)!
                            },
                            query: {
                                requestKey: requestKey,
                            }
                        })
                    } catch (err) {
                        logger.error("Failed to create label data", { error: err, requestKey, labelGroupId: idRepo.getServerId("labelGroup", provisionalGroupId)! })
                        throw new ConnectionError("Failed to create label data", err)
                    }
                    if (!resp.data) {
                        if (isRequestConflictErrorResponse(resp.error) && resp.error.detail.cacheConflict) {
                            throw new CacheConflictError("Request key conflict while creating label data", requestKey)
                        } else if (isDetailHttpErrorResponse(resp.error)) {
                            throw new FatalError(`Failed to create label data: ${resp.error.detail}`, resp.error)
                        }
                        throw new FatalError("Failed to create label data", resp.error)
                    }
                    idRepo.bindServerId("labelData", provisionalDataId, resp.data.labelDataId)
                    entries.find((entry) => entry.labelGroup.labelGroupId === provisionalGroupId)!.loadingStatus = "loaded"
                    labelGroupSyncHandler()
                    return null
                },
                handleCachedResult: (cachedResult, requestKey) => {
                    if (cachedResult.status === "success") {
                        const validated = validateData(isLabelData, cachedResult.response)
                        idRepo.bindServerId("labelData", provisionalDataId, validated.labelDataId)
                        entries.find((entry) => entry.labelGroup.labelGroupId === provisionalGroupId)!.loadingStatus = "loaded"
                        labelGroupSyncHandler()
                        return { status: cachedResult.status, signal: null, error : null }
                    }
                    else if (cachedResult.status === "pending") {
                        return { status: cachedResult.status, signal: null, error : null }
                    }
                    else {
                        if (cachedResult.error?.cacheConflict) {
                            return { status: cachedResult.status, signal: null, error : new CacheConflictError("Request key conflict while creating label data", requestKey) }
                        }
                        return { status: cachedResult.status, signal: null, error : new FatalError("Failed to create label data", cachedResult.error instanceof Error ? cachedResult.error : new Error(JSON.stringify(cachedResult.error))) }
                    }
                    
                },
                reservationRequest: {
                    reserveList: [ { id : provisionalDataId, kind: "labelData", desiredState: "creating" }, { id : provisionalGroupId, kind: "labelGroup", desiredState: "locked" }, { id : contentIdSnapshot, kind : "chapterContent", desiredState : "locked"} ],
                    skip: () => skipRemaining,
                },
                onFailure: cleanupAddLabelGroupFailure,
                onFatalError: cleanupAddLabelGroupFailure,
            }
        ]]
    }

    const addLabel = (labelGroupId : string, labelDataId : string, startPos : number, endPos : number, word : string, entityGroup? : string, score? : number, dirty? : boolean) : ProvisionalId => {
        ensureNoPendingTextOps()
        if (startPos < 0 || startPos >= endPos || endPos > text.length) {
            throw new Error("Label bounds are out of range")
        }
        if (word.length !== endPos - startPos) {
            throw new Error("Label word length must match label bounds")
        }
        if (text.slice(startPos, endPos) !== word) {
            throw new Error("Label word must match the current chapter text")
        }
        const provisionalLabelId = idRepo.newId("label")
        const entriesCopy = [...entries]
        const entryIndex = entriesCopy.findIndex(e => e.labelGroup.labelGroupId === labelGroupId)
        if (entryIndex === -1) {
            throw new Error(`Label group with id ${labelGroupId} not found`)
        }
        const entry = entriesCopy[entryIndex]
        if (entry.labels.some(l => Math.max(l.labelStart, startPos) < Math.min(l.labelEnd, endPos) )) { // if any label overlaps with [startPos, endPos)
            throw new Error("Label overlaps with existing label")
        } 

        entriesCopy[entryIndex].labels.push({
            labelId: provisionalLabelId,
            labelDataId: labelDataId,
            labelStart: startPos,
            labelEnd: endPos,
            labelWord: word,
            provisional: true,
            labelDirty: dirty ?? true,
            labelEntityGroup: entityGroup ?? null,
            labelScore: score ?? 1.0,
        })
        entriesCopy[entryIndex].labels.sort((left, right) => left.labelStart - right.labelStart)
        queueLabelOp(labelGroupId, provisionalLabelId, {
            op: "add",
            startPos: startPos,
            endPos: endPos,
            word: word,
            entityGroup: entityGroup ?? null,
            score: score ?? 1.0,
            dirty: dirty ?? true,
        })
        entries = entriesCopy
        return provisionalLabelId
    }

    const deleteLabel = (labelGroupId : string, labelDataId : string, startPos : number, endPos : number) : ProvisionalId => {
        ensureNoPendingTextOps()
        const entriesCopy = [...entries]
        const entryIndex = entriesCopy.findIndex((entry) => entry.labelGroup.labelGroupId === labelGroupId)
        if (entryIndex === -1) {
            throw new Error(`Label group with id ${labelGroupId} not found`)
        }
        const entry = entriesCopy[entryIndex]
        const labelIndex = getMatchingLabelIndex(entry, startPos, endPos)
        if (labelIndex === -1) {
            throw new Error(`Label [${startPos}, ${endPos}) not found in label group ${labelGroupId}`)
        }
        const label = entry.labels[labelIndex]
        if (label.labelDataId !== labelDataId) {
            throw new Error(`Label does not belong to label data ${labelDataId}`)
        }

        entriesCopy[entryIndex] = {
            ...entry,
            labels: entry.labels.filter((_, idx) => idx !== labelIndex),
        }
        queueLabelOp(labelGroupId, label.labelId, {
            op: "delete",
            startPos: label.labelStart,
            endPos: label.labelEnd,
            word: label.labelWord,
        })
        entries = entriesCopy
        return label.labelId
    }

    const updateLabel = (
        labelGroupId : string,
        labelDataId : string,
        startPos : number,
        endPos : number,
        newStartPos? : number | null,
        newEndPos? : number | null,
        newWord? : string | null,
        entityGroup? : string,
        score? : number,
        dirty? : boolean,
    ) : ProvisionalId => {
        ensureNoPendingTextOps()
        const entriesCopy = [...entries]
        const entryIndex = entriesCopy.findIndex((entry) => entry.labelGroup.labelGroupId === labelGroupId)
        if (entryIndex === -1) {
            throw new Error(`Label group with id ${labelGroupId} not found`)
        }
        const entry = entriesCopy[entryIndex]
        const labelIndex = getMatchingLabelIndex(entry, startPos, endPos)
        if (labelIndex === -1) {
            throw new Error(`Label [${startPos}, ${endPos}) not found in label group ${labelGroupId}`)
        }
        const currentLabel = entry.labels[labelIndex]
        if (currentLabel.labelDataId !== labelDataId) {
            throw new Error(`Label does not belong to label data ${labelDataId}`)
        }

        const nextStart = newStartPos ?? currentLabel.labelStart
        const nextEnd = newEndPos ?? currentLabel.labelEnd
        const boundsChanged = newStartPos != null || newEndPos != null
        if (!boundsChanged && newWord != null) {
            throw new Error("Cannot set a new label word without changing label bounds")
        }
        const nextWord = newWord ?? (boundsChanged ? text.slice(nextStart, nextEnd) : currentLabel.labelWord)
        if (nextStart >= nextEnd) {
            throw new Error("Updated label must have start < end")
        }
        if (nextStart < 0 || nextEnd > text.length) {
            throw new Error("Updated label bounds are out of range")
        }
        if (nextWord.length !== nextEnd - nextStart) {
            throw new Error("Updated label word length must match updated bounds")
        }
        if (text.slice(nextStart, nextEnd) !== nextWord) {
            throw new Error("Updated label word must match the current chapter text")
        }
        const overlapsExisting = entry.labels.some((label, idx) => {
            if (idx === labelIndex) {
                return false
            }
            return Math.max(label.labelStart, nextStart) < Math.min(label.labelEnd, nextEnd)
        })
        if (overlapsExisting) {
            throw new Error("Updated label overlaps with existing label")
        }

        entriesCopy[entryIndex] = {
            ...entry,
            labels: entry.labels.map((label, idx) => {
                if (idx !== labelIndex) {
                    return label
                }
                return {
                    ...label,
                    labelStart: nextStart,
                    labelEnd: nextEnd,
                    labelWord: nextWord,
                    labelEntityGroup: entityGroup ?? label.labelEntityGroup,
                    labelScore: score ?? label.labelScore,
                    labelDirty: dirty ?? label.labelDirty,
                }
            }).sort((left, right) => left.labelStart - right.labelStart),
        }

        queueLabelOp(labelGroupId, currentLabel.labelId, {
            op: "update",
            startPos: currentLabel.labelStart,
            endPos: currentLabel.labelEnd,
            word: currentLabel.labelWord,
            newStartPos: nextStart !== currentLabel.labelStart ? nextStart : undefined,
            newEndPos: nextEnd !== currentLabel.labelEnd ? nextEnd : undefined,
            newWord: nextWord !== currentLabel.labelWord ? nextWord : undefined,
            entityGroup: entityGroup ?? undefined,
            score: score ?? undefined,
            dirty: dirty ?? undefined,
        })
        entries = entriesCopy
        return currentLabel.labelId
    }

    const flushLabelOps = () : RequestEvent[] => {
        const queuedOps = Array.from(labelOpQueue.entries()).filter(([, ops]) => ops.length > 0)
        labelOpQueue = new Map()
        return queuedOps.map(([labelGroupId, queuedLabelOps]) => {
            const entry = entries.find((candidate) => candidate.labelGroup.labelGroupId === labelGroupId)
            if (!entry) {
                throw new Error(`Label group with id ${labelGroupId} not found while flushing label ops`)
            }
            const currentLabelIds = new Set(entry.labels.map((label) => label.labelId))
            const reserveList : { id : ProvisionalId, kind : Kind, desiredState : InFlightIdStatus }[] = [
                { id: entry.labelData.labelDataId, kind: "labelData", desiredState: "updating" },
                { id: chapterContentId, kind: "chapterContent", desiredState: "locked" },
            ]
            const reservedLabelIds = new Set<ProvisionalId>()
            for (const { labelId } of queuedLabelOps) {
                if (reservedLabelIds.has(labelId)) {
                    continue
                }
                reservedLabelIds.add(labelId)
                const currentState = idRepo.idObjState("label", labelId)
                const labelStillExists = currentLabelIds.has(labelId)
                if (currentState === "pending" && !labelStillExists) {
                    continue
                }
                if (currentState === "pending") {
                    reserveList.push({ id: labelId, kind: "label", desiredState: "creating" })
                }
                else if (labelStillExists) {
                    reserveList.push({ id: labelId, kind: "label", desiredState: "updating" })
                }
                else {
                    reserveList.push({ id: labelId, kind: "label", desiredState: "deleting" })
                }
            }
            return {
                variant: "labelOp",
                retries: 3,
                reservationRequest: {
                    reserveList,
                },
                
                callback: async (requestKey) => {
                    let resp
                    try {
                        resp = await updateLabelDataStreamLabelDatasLabelDataIdPatch({
                            path: {
                                labelDataId: idRepo.getServerId("labelData", entry.labelData.labelDataId)!,
                            },
                            body: {
                                ops: queuedLabelOps.map(({ op }) => op),
                            },
                            query: {
                                requestKey: requestKey,
                            }
                        })
                    } catch (err) {
                        logger.error("Failed to update label data stream", { error: err, labelDataId: idRepo.getServerId("labelData", entry.labelData.labelDataId)!, requestKey })
                        throw new ConnectionError("Failed to update label data stream", err)
                    }
                    if (resp.error) {
                        if (isRequestConflictErrorResponse(resp.error) && resp.error.detail.cacheConflict) {
                            throw new CacheConflictError("Request key conflict while updating label data stream", requestKey)
                        } else if (isDetailHttpErrorResponse(resp.error)) {
                            throw new FatalError(`Failed to update label data stream: ${resp.error.detail}`, resp.error)
                        }
                        throw new FatalError("Failed to update label data stream", resp.error)
                    }
                    
                    for (const { labelId, op } of queuedLabelOps) {
                        if (op.op === "add" && currentLabelIds.has(labelId)) {
                            idRepo.bindServerExists("label", labelId)
                        }
                    }
                    return null
                },
                handleCachedResult: (cachedResult, requestKey) => {
                    if (cachedResult.status === "success") {
                        for (const { labelId, op } of queuedLabelOps) {
                            if (op.op === "add" && currentLabelIds.has(labelId)) {
                                idRepo.bindServerExists("label", labelId)
                            }
                        }
                        return { status: cachedResult.status, signal: null, error : null }
                    }
                    else if (cachedResult.status === "pending") {
                        return { status: cachedResult.status, signal: null, error : null }
                    }
                    else {
                        if (cachedResult.error?.cacheConflict) {
                            return { status: cachedResult.status, signal: null, error : new CacheConflictError("Request key conflict while updating label data stream", requestKey) }
                        }
                        return { status: cachedResult.status, signal: null, error : new FatalError("Failed to update label data stream", cachedResult.error instanceof Error ? cachedResult.error : new Error(JSON.stringify(cachedResult.error))) }
                    }
                }
            }
        })
    }

    const insertTextAt = (pos : number, insertedText : string) : void => {
        ensureNoPendingLabelOps()
        const currentText = text
        if (pos < 0 || pos > currentText.length) {
            throw new Error("Insert position is out of bounds")
        }
        if (insertedText.length === 0) {
            return
        }
        const affectedLabelDataIds = entries.map((entry) => entry.labelData.labelDataId)
        const affectedLabelIds = entries.flatMap((entry) => entry.labels.map((label) => label.labelId))
        const delta = insertedText.length
        const nextEntries = entries.map((entry) => {
            const nextLabels = entry.labels
                .filter((label) => label.labelEnd <= pos || label.labelStart >= pos)
                .map((label) => {
                    if (label.labelStart >= pos) {
                        return {
                            ...label,
                            labelStart: label.labelStart + delta,
                            labelEnd: label.labelEnd + delta,
                        }
                    }
                    return label
                })
                .sort((left, right) => left.labelStart - right.labelStart)
            return {
                ...entry,
                labels: nextLabels,
            }
        })
        entries = nextEntries
        text = currentText.slice(0, pos) + insertedText + currentText.slice(pos)
        textOpQueue.push({
            op: {
                op: "insert",
                start: pos,
                text: insertedText,
            },
            labelDataIds: affectedLabelDataIds,
            labelIds: affectedLabelIds,
        })
    }

    const deleteTextAt = (startPos : number, length : number) : void => {
        ensureNoPendingLabelOps()
        const currentText = text
        const endPos = startPos + length
        if (startPos < 0 || startPos > currentText.length || endPos < startPos || endPos > currentText.length) {
            throw new Error("Delete text range is out of bounds")
        }
        const deletedText = currentText.slice(startPos, endPos)
        if (deletedText.length === 0) {
            return
        }
        const affectedLabelDataIds = entries.map((entry) => entry.labelData.labelDataId)
        const affectedLabelIds = entries.flatMap((entry) => entry.labels.map((label) => label.labelId))
        const delta = deletedText.length
        const nextEntries = entries.map((entry) => {
            const nextLabels = entry.labels
                .filter((label) => label.labelEnd <= startPos || label.labelStart >= endPos)
                .map((label) => {
                    if (label.labelStart >= endPos) {
                        return {
                            ...label,
                            labelStart: label.labelStart - delta,
                            labelEnd: label.labelEnd - delta,
                        }
                    }
                    return label
                })
                .sort((left, right) => left.labelStart - right.labelStart)
            return {
                ...entry,
                labels: nextLabels,
            }
        })
        entries = nextEntries
        text = currentText.slice(0, startPos) + currentText.slice(endPos)
        textOpQueue.push({
            op: {
                op: "delete",
                start: startPos,
                text: deletedText,
            },
            labelDataIds: affectedLabelDataIds,
            labelIds: affectedLabelIds,
        })
    }

    const flushTextOps = () : RequestEvent[] => {
        if (textOpQueue.length === 0) {
            return []
        }
        const queuedTextOps = [...textOpQueue]
        textOpQueue = []
        const currentChapterContentId = chapterContentId
        const reserveLabelDataIds = Array.from(new Set(queuedTextOps.flatMap(({ labelDataIds }) => labelDataIds)))
        const reserveLabelIds = Array.from(new Set(queuedTextOps.flatMap(({ labelIds }) => labelIds)))
        const snapshot = [...entries]
        return [
            {
                variant: "textOp",
                retries: 3,
                reservationRequest: {
                    reserveList: [
                        { id: currentChapterContentId, kind: "chapterContent", desiredState: "updating" },
                        ...reserveLabelDataIds.map((labelDataId) => ({ id: labelDataId, kind: "labelData" as const, desiredState: "idUpdating" as const })),
                        ...reserveLabelIds.map((labelId) => ({ id: labelId, kind: "label" as const, desiredState: "updating" as const })),
                    ]
                },
                callback: async (requestKey) => {
                    let resp
                    try {
                        resp = await updateChapterContentChaptersChapterIdContentPatch({
                            path: {
                                chapterId: chapter.chapterId,
                            },
                            body: {
                                chapterContentId: idRepo.getServerId("chapterContent", currentChapterContentId)!,
                                textOps: queuedTextOps.map(({ op }) => op),
                            },
                            query: {
                                requestKey: requestKey,
                            }
                        })
                    } catch (err) {
                        logger.error("Failed to modify chapter content", { error: err, chapterContentId: idRepo.getServerId("chapterContent", currentChapterContentId)!, requestKey })
                        throw new ConnectionError("Failed to modify chapter content", err)
                    }
                    if (!resp.data) {
                        if (isRequestConflictErrorResponse(resp.error) && resp.error.detail.cacheConflict) {
                            throw new CacheConflictError("Request key conflict while modifying chapter content", requestKey)
                        } else if (isDetailHttpErrorResponse(resp.error)) {
                            throw new FatalError(`Failed to modify chapter content: ${resp.error.detail}`, resp.error)
                        }
                        throw new FatalError("Failed to modify chapter content", resp.error)
                    }
                    idRepo.bindServerId("chapterContent", currentChapterContentId, resp.data.chapterContentId)
                    for (const entry of snapshot) {
                        const oldServerLabelDataId = idRepo.getServerId("labelData", entry.labelData.labelDataId)
                        if (oldServerLabelDataId === null) {
                            throw new Error(`Label data ${entry.labelData.labelDataId} is not bound to a server id`)
                        }
                        const nextServerLabelDataId = resp.data.labelDataIdMap[oldServerLabelDataId]
                        if (!nextServerLabelDataId) {
                            throw new Error(`Missing label data remap for server label data id ${oldServerLabelDataId}`)
                        }
                        idRepo.bindServerId("labelData", entry.labelData.labelDataId, nextServerLabelDataId)
                    }
                    return null
                },
                handleCachedResult: (cachedResult, requestKey) => {
                    if (cachedResult.status === "success") {
                        const validated = validateData(isModifyChapterContentResponse, cachedResult.response)
                        idRepo.bindServerId("chapterContent", currentChapterContentId, validated.chapterContentId)
                        for (const entry of snapshot) {
                            const oldServerLabelDataId = idRepo.getServerId("labelData", entry.labelData.labelDataId)
                            if (oldServerLabelDataId === null) {
                                throw new Error(`Label data ${entry.labelData.labelDataId} is not bound to a server id`)
                            }
                            const nextServerLabelDataId = validated.labelDataIdMap[oldServerLabelDataId]
                            if (!nextServerLabelDataId) {
                                throw new Error(`Missing label data remap for server label data id ${oldServerLabelDataId}`)
                            }
                            idRepo.bindServerId("labelData", entry.labelData.labelDataId, nextServerLabelDataId)
                        }
                        return { status: cachedResult.status, signal: null, error : null }
                    }
                    else if (cachedResult.status === "pending") {
                        return { status: cachedResult.status, signal: null, error : null }
                    }
                    else {
                        if (cachedResult.error?.cacheConflict) {
                            return { status: cachedResult.status, signal: null, error : new CacheConflictError("Request key conflict while modifying chapter content", requestKey) }
                        }
                        return { status: cachedResult.status, signal: null, error : new FatalError("Failed to modify chapter content", cachedResult.error instanceof Error ? cachedResult.error : new Error(JSON.stringify(cachedResult.error))) }
                    }
                }
            },
        ]
    }

    const handleSignal = (signal : DecoratedSignal) => {
        logger.info("Received signal in data manager:", signal)
        return
    }

    const getGroups = () => entries.map((entry) => entry.labelGroup)

    const reloadGroup = (labelGroupId : string) : RequestEvent[] => {
        const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId)
        if (!entry) {
            throw new Error(`Label group with id ${labelGroupId} not found`)
        }
        if (entry.loadingStatus === "loading") {
            return []
        }
        const contentIdSnapshot = entry.labelData.chapterContentId
        const oldLabelDataSnapshot = entry.labelData
        const oldLabelDataId = oldLabelDataSnapshot.labelDataId
        const oldLabelsSnapshot = [...entry.labels]
        const oldLabelIds = oldLabelsSnapshot.map((label) => label.labelId)
        const newLabelDataId = idRepo.newId("labelData")
        entry.loadingStatus = "loading"
        labelGroupSyncHandler()
        let skipRemaining = false

        const cleanupReloadFailure = () => {
            entry.loadingStatus = "loadError"
            skipRemaining = true
            if (idRepo.isReserveable("labelData", newLabelDataId, "killing")) {
                idRepo.reserveIdObjState("labelData", newLabelDataId, "killing")
                idRepo.releaseIdObjStateOnSuccess("labelData", newLabelDataId)
            }
            else if (idRepo.isReserveable("labelData", newLabelDataId, "detaching")) {
                idRepo.reserveIdObjState("labelData", newLabelDataId, "detaching")
                idRepo.releaseIdObjStateOnSuccess("labelData", newLabelDataId)
            }
            labelGroupSyncHandler()
        }

        return [
            {
                variant: "reloadGroup",
                retries: 3,
                reservationRequest: {
                    reserveList: [
                        {
                            id: entry.labelGroup.labelGroupId,
                            kind: "labelGroup",
                            desiredState: "updating",
                        },
                    ],
                    skip: () => skipRemaining,
                },
                callback: async () => {
                    let resp
                    try {
                        resp = await Promise.all([
                            readLabelGroupLabelGroupsLabelGroupIdGet({
                                path: {
                                    labelGroupId: idRepo.getServerId("labelGroup", entry.labelGroup.labelGroupId)!,
                                }
                            }),
                            readLabelContributorsLabelGroupsLabelGroupIdContributorsGet({
                                path: {
                                    labelGroupId: idRepo.getServerId("labelGroup", entry.labelGroup.labelGroupId)!,
                                }
                            })
                        ])
                    } catch (err) {
                        logger.error("Failed to read label group or contributors during reload", { error: err, labelGroupId: entry.labelGroup.labelGroupId })
                        throw new ConnectionError("Failed to read label group", err)
                    }
                    if (resp[0].error || resp[1].error) {
                        logger.error("Failed to read label group or contributors during reload", { errors: [resp[0].error, resp[1].error], labelGroupId: entry.labelGroup.labelGroupId })
                        throw new FatalError("Failed to read label group", resp[0].error ?? resp[1].error)
                    }
                    entry.labelGroup = {
                        ...entry.labelGroup,
                        labelGroupName: resp[0].data.labelGroupName,
                    }
                    const contributorMe = resp[1].data.find((contributor) => contributor.userId === userId)
                    if (!contributorMe) {
                        throw new FatalError("Current user is not a contributor to the label group")
                    }
                    entry.role = contributorMe.labelContributorRole
                    return null
                },
                onFailure: cleanupReloadFailure,
                onFatalError: cleanupReloadFailure
            },
            {
                variant: "reloadGroup",
                retries: 3,
                reservationRequest: {
                    reserveList: [],
                },
                callback: async () => {
                    entry.labels = []
                    return oldLabelIds.length > 0 ? { type: "clearLabels", labelIds: oldLabelIds } : null
                },
                onFailure: cleanupReloadFailure,
                onFatalError: cleanupReloadFailure
            },
            {
                variant: "reloadGroup",
                retries: 3,
                reservationRequest: {
                    reserveList: makeIdempotent(() => [
                        ...(() : Reservation[] => {
                            if (idRepo.isReserveable("labelData", oldLabelDataId, "detaching")) {
                                return [{
                                    id: oldLabelDataId,
                                    kind: "labelData",
                                    desiredState: "detaching"
                                }]
                            }
                            else if (idRepo.isReserveable("labelData", oldLabelDataId, "killing")) {
                                return [{
                                    id: oldLabelDataId,
                                    kind: "labelData",
                                    desiredState: "killing"
                                }]
                            }
                            else {
                                return []
                            }
                        })(),
                        ...oldLabelsSnapshot.filter((label) => idRepo.isReserveable("label", label.labelId, "detaching")).map((label) : { id: string, kind: Kind, desiredState: InFlightIdStatus } => ({
                            id: label.labelId,
                            kind: "label",
                            desiredState: "detaching"
                        })),
                        ...oldLabelsSnapshot.filter((label) => !idRepo.isReserveable("label", label.labelId, "detaching") && idRepo.isReserveable("label", label.labelId, "killing")).map((label) : { id: string, kind: Kind, desiredState: InFlightIdStatus } => ({
                            id: label.labelId,
                            kind: "label",
                            desiredState: "killing"
                        })),
                    ]),
                    skip: () => skipRemaining,
                    wait: () => {
                        return isInFlight(idRepo.idObjState("labelData", oldLabelDataId)) || oldLabelsSnapshot.some((label) => isInFlight(idRepo.idObjState("label", label.labelId)))
                    }
                },
                callback: async () => null,
                onFailure: cleanupReloadFailure,
                onFatalError: cleanupReloadFailure
            },
            {
                variant: "reloadGroup",
                retries: 3,
                reservationRequest: {
                    reserveList: [
                        {
                            id: entry.labelGroup.labelGroupId,
                            kind: "labelGroup",
                            desiredState: "locked",
                        },
                        {
                            id: newLabelDataId,
                            kind: "labelData",
                            desiredState: "loading",
                        },
                    ],
                    skip: () => skipRemaining,
                },  
                callback: async () => {
                    let resp
                    try {
                        resp = await readLabelDatasByGroupChaptersLabelDatasGet({
                            query: {
                                labelGroupId: idRepo.getServerId("labelGroup", entry.labelGroup.labelGroupId)!,
                                start: chapter.chapterNum,
                                end: chapter.chapterNum + 1,
                            }
                        })
                    } catch (err) {
                        logger.error("Failed to read label data", { error: err, labelGroupId: entry.labelGroup.labelGroupId })
                        throw new ConnectionError("Failed to read label data", err)
                    }
                    if (resp.error) {
                        logger.error("Failed to read label data", { errors: [resp.error], labelGroupId: entry.labelGroup.labelGroupId })
                        throw new FatalError("Failed to read label data", resp.error)
                    }
                    if (resp.data.length === 0) {
                        logger.error("No label data found for label group and chapter", { labelGroupId: entry.labelGroup.labelGroupId, chapterNum: chapter.chapterNum })
                        throw new FatalError("No label data found for label group and chapter")
                    }
                    idRepo.bindServerId("labelData", newLabelDataId, resp.data[0].labelDataId)
                    entry.labelData = {
                        ...oldLabelDataSnapshot,
                        labelDataId: newLabelDataId,
                    }
                    return null
                },
                onFailure: cleanupReloadFailure,
                onFatalError: cleanupReloadFailure
            },
            {
                variant: "reloadGroup",
                reservationRequest: {
                    reserveList: [
                        {
                            id: contentIdSnapshot,
                            kind: "chapterContent",
                            desiredState: "locked",
                        },
                        {
                            id: entry.labelGroup.labelGroupId,
                            kind: "labelGroup",
                            desiredState: "locked",
                        },
                        {
                            id: newLabelDataId,
                            kind: "labelData",
                            desiredState: "locked",
                        }
                    ],
                    skip: () => skipRemaining,
                },
                retries: 3,
                callback: async () => {
                    let resp
                    try {
                        resp = await readLabelsByLabelDataLabelDatasLabelDataIdLabelsGet({
                            path: {
                                labelDataId: idRepo.getServerId("labelData", newLabelDataId)!,
                            }
                        })
                    } catch (err) {
                        logger.error("Failed to read labels for label data", { error: err, labelDataId: idRepo.getServerId("labelData", newLabelDataId)! })
                        throw new ConnectionError("Failed to read labels for label data", err)
                    }
                    if (resp.error) {
                        logger.error("Failed to read labels for label data", { errors: [resp.error], labelDataId: idRepo.getServerId("labelData", newLabelDataId)! })
                        throw new FatalError("Failed to read labels for label data", resp.error)
                    }
                    const newLabels = resp.data.map((label) : ProvisionalLabel => ({ ...label, provisional: true, labelId: idRepo.newIdAndBindExists("label") })) // possible leak here if timeout but it doesn't really matter
                    entry.labels = newLabels
                    entry.loadingStatus = "loaded"
                    labelGroupSyncHandler()
                    return { type: "groupLoaded", labelGroupId: entry.labelGroup.labelGroupId, getLabels: () => newLabels, mutable: entry.role === "editor" || entry.role === "owner" } 
                },
                onFailure: cleanupReloadFailure,
                onFatalError: cleanupReloadFailure
            },
        ]
    }

    const getLabelDataId = (labelGroupId : string) => {
        const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId)
        if (!entry) {
            throw new Error(`Label group with id ${labelGroupId} not found`)
        }
        return entry.labelData.labelDataId
    }

    const getRole = (labelGroupId : string) => {
        const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId)
        if (!entry) {
            throw new Error(`Label group with id ${labelGroupId} not found`)
        }
        return entry.role
    }

    const getLabels = (labelGroupId : string) => {
        const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId)
        if (!entry) {
            throw new Error(`Label group with id ${labelGroupId} not found`)
        }
        return entry.labels
    }

    const getLoadingStatus = (labelGroupId : string) => {
        const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId)
        if (!entry) {
            throw new Error(`Label group with id ${labelGroupId} not found`)
        }
        return entry.loadingStatus
    }
    
    const getName = (labelGroupId : string) => {
        const entry = entries.find((e) => e.labelGroup.labelGroupId === labelGroupId)
        if (!entry) {
            throw new Error(`Label group with id ${labelGroupId} not found`)
        }
        return entry.labelGroup.labelGroupName
    }


    const attachLabelGroupSyncHandler = (handler : () => void) => {
        labelGroupSyncHandler = handler
    }

    const detachLabelGroupSyncHandler = () => {
        labelGroupSyncHandler = () => {}
    }

    return {
        addLabel: addLabel,
        addLabelGroup: addLabelGroup,
        deleteLabel,
        updateLabel,
        flushLabelOps,
        insertTextAt,
        deleteTextAt,
        flushTextOps,
        handleSignal,
        reloadGroup,

        getForGroup: {
            labelDataId: getLabelDataId,
            role: getRole,
            labels: getLabels,
            loadingStatus: getLoadingStatus,
            name: getName,
        },

        getGroups,
        attachLabelGroupSyncHandler,
        detachLabelGroupSyncHandler
    }
}
