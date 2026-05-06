import type { IDRepository, IdentifiableKindMap, ExistableKindMap, IdStatus, InFlightIdStatus, ServerExists, ServerId, ProvisionalId, Kind, IdentifiableKind, ExistableKind } from "./types";
import { isIdentifiableKind, isInFlight, entryStatus, exitStatus } from "./types";

/**
 * As the current data model stands, most objects have an underlying ID. In order to synchronize the IDs that appear on the frontend and backend without sacrificing client responsiveness, we need a way to bridge the gap between client-side IDs and server-side IDs. This repository serves as a central place to manage this mapping and the state of these IDs.
 * 
 * The ID repository provides the following functionalities:
 * 
 * Generating new provisional IDs for objects that are being created on the client side but have not yet been persisted to the server.
 * Binding provisional IDs to server IDs once the server responds with the created object.
 * Tracking the existence of objects that may not have a server ID but are known to exist on the server.
 * Managing the state of IDs to prevent race conditions and ensure that operations on objects are performed in a consistent manner.
 * 
 * The way it does so is as follows:
 * - Each provisional ID is keyed using a combination of its kind (e.g., "labelGroup", "labelData", "chapterContent") and a unique identifier (e.g., "provisional-1", "provisional-2", etc.).
 * - For each provisional ID, we associate it with a server ID (possibly null if it has not yet been created on the server) and a status (see types.ts for the possible statuses and state transitions).
 * - Any given provisional ID can be reserved for a specific state transition (e.g., from "pending" to "creating", from "clean" to "updating", etc.) if it is currently in the appropriate state and has the appropriate server ID existence status.
 * - Once an ID is reserved for a state transition, it cannot be reserved for another transition until it is released. The exception to this is the "locked" state, which can be reserved multiple times and only transitions back to "clean" once all locks are released.
 * - The repository provides methods to release reserved states on both success and failure, which will transition the ID to the appropriate next state based on the outcome of the operation.
 * 
 * By centralizing this logic in a repository, we can ensure that all components that need to interact with IDs do so in a consistent manner, reducing the likelihood of bugs and race conditions related to ID management.
 */
export function buildIdRepository() : IDRepository {
    let counterRef = 0
    const identifiableKindMap : IdentifiableKindMap = {
        labelGroup : new Map<ProvisionalId, { serverId : ServerId | null, status : IdStatus, lockCount : number }>(),
        labelData : new Map<ProvisionalId, { serverId : ServerId | null, status : IdStatus, lockCount : number }>(),
        chapterContent : new Map<ProvisionalId, { serverId : ServerId | null, status : IdStatus, lockCount : number }>(),
    }

    const existableKindMap : ExistableKindMap = {
        label : new Map<ProvisionalId, { serverExists : ServerExists | null, status : IdStatus, lockCount : number }>(),
    }

    return {
        newId(kind : Kind) : ProvisionalId {
            if (isIdentifiableKind(kind)) {
                const id = `provisional-${counterRef++}`
                identifiableKindMap[kind].set(id, { serverId: null, status: "pending", lockCount: 0 })
                return id
            }
            else {
                const id = `provisional-${counterRef++}`
                existableKindMap[kind].set(id, { serverExists: null, status: "pending", lockCount: 0 })
                return id
            }
        },

        newIdAndBindId(kind : IdentifiableKind, serverId : string) : ProvisionalId {
            const id = `provisional-${counterRef++}`
            identifiableKindMap[kind].set(id, { serverId, status: "clean", lockCount: 0 })
            return id
        },

        newIdAndBindExists(kind : ExistableKind) : ProvisionalId {
            const id = `provisional-${counterRef++}`
            existableKindMap[kind].set(id, { serverExists: true, status: "clean", lockCount: 0 })
            return id
        },

        getServerId(kind : IdentifiableKind, provisionalId : ProvisionalId) : ServerId | null {
            const entry = identifiableKindMap[kind].get(provisionalId)
            if (!entry) throw new Error(`Provisional id ${provisionalId} not found for kind ${kind}`)
            return entry.serverId
        },

        getServerExists(kind : ExistableKind, provisionalId : ProvisionalId) : ServerExists | null {
            const entry = existableKindMap[kind].get(provisionalId)
            if (!entry) throw new Error(`Provisional id ${provisionalId} not found for kind ${kind}`)
            return entry.serverExists
        },

        bindServerId(kind : IdentifiableKind, provisionalId : ProvisionalId, serverId : ServerId) : void {
            const entry = identifiableKindMap[kind].get(provisionalId)
            if (!entry) throw new Error(`Provisional id ${provisionalId} not found for kind ${kind}`)
            entry.serverId = serverId
        },

        bindServerExists(kind : ExistableKind, provisionalId : ProvisionalId) : void {
            const entry = existableKindMap[kind].get(provisionalId)
            if (!entry) throw new Error(`Provisional id ${provisionalId} not found for kind ${kind}`)
            entry.serverExists = true
        },

        idObjState(kind : Kind, id : string) : IdStatus {
            if (isIdentifiableKind(kind)) {
                const entry = identifiableKindMap[kind].get(id)
                if (!entry) throw new Error(`Provisional id ${id} not found for kind ${kind}`)
                return entry.status
            }
            else {
                const entry = existableKindMap[kind].get(id)
                if (!entry) throw new Error(`Provisional id ${id} not found for kind ${kind}`)
                return entry.status
            }
        },

        isReserveable(kind : Kind, id : ProvisionalId, desiredState : InFlightIdStatus) : boolean {
            const currentState = this.idObjState(kind, id)
            const serverState = isIdentifiableKind(kind) ? identifiableKindMap[kind].get(id)?.serverId : existableKindMap[kind].get(id)?.serverExists
            if (desiredState === "creating") {
                return currentState === "pending" && serverState === null
            }
            else if (desiredState === "updating" || desiredState === "idUpdating") {
                return currentState === "clean" && serverState !== null
            }
            else if (desiredState == "locked") {
                return (currentState === "clean" || currentState === "locked") && serverState !== null
            }
            else if (desiredState === "deleting") {
                return currentState === "clean" && serverState !== null
            }
            else if (desiredState === "detaching") {
                return currentState === "clean" && serverState !== null
            }
            else if (desiredState === "loading") {
                return currentState === "pending"
            }
            else if (desiredState === "killing") {
                return currentState === "pending"
            }
            else {
                return false
            }
        },

        reserveIdObjState(kind : Kind, id : ProvisionalId, desiredState : InFlightIdStatus) : boolean {
            if (!this.isReserveable(kind, id, desiredState)) {
                return false
            }
            const entry = isIdentifiableKind(kind) ? identifiableKindMap[kind].get(id)! : existableKindMap[kind].get(id)!
            entry.status = desiredState
            if (desiredState === "locked") {
                entry.lockCount += 1
            }
            return true
        },

        releaseIdObjStateOnSuccess(kind : Kind, id : ProvisionalId) : void {
            const entry = isIdentifiableKind(kind) ? identifiableKindMap[kind].get(id)! : existableKindMap[kind].get(id)!
            if (!entry || !isInFlight(entry.status)) {
                return
            }
            if (entry.status === "locked") {
                entry.lockCount = Math.max(0, entry.lockCount - 1)
                if (entry.lockCount >= 1) {
                    return
                }
            }
            entry.status = exitStatus(entry.status)
        },

        releaseIdObjStateOnFailure(kind : Kind, id : ProvisionalId) : void {
            const entry = isIdentifiableKind(kind) ? identifiableKindMap[kind].get(id) : existableKindMap[kind].get(id)
            if (!entry || !isInFlight(entry.status)) {
                return
            }
            if (entry.status === "locked") {
                entry.lockCount = Math.max(0, entry.lockCount - 1)
                if (entry.lockCount >= 1) {
                    return
                }
            }
            entry.status = entryStatus(entry.status)
        },

        gc() : void {
            identifiableKindMap.labelGroup.forEach((value, key) => {
                if (value.status === "deleted" || value.status === "killed" || value.status === "detached") {
                    identifiableKindMap.labelGroup.delete(key)
                }
            })
            identifiableKindMap.labelData.forEach((value, key) => {
                if (value.status === "deleted" || value.status === "killed" || value.status === "detached") {
                    identifiableKindMap.labelData.delete(key)
                }
            })
            identifiableKindMap.chapterContent.forEach((value, key) => {
                if (value.status === "deleted" || value.status === "killed" || value.status === "detached") {
                    identifiableKindMap.chapterContent.delete(key)
                }
            })
            existableKindMap.label.forEach((value, key) => {
                if (value.status === "deleted" || value.status === "killed" || value.status === "detached") {
                    existableKindMap.label.delete(key)
                }
            })
        }
    }
}
