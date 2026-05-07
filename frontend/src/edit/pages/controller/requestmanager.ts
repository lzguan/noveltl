import type { CachedKeyedRequestEvent, IDRepository, KeyedRequestEvent, RequestEvent, RequestManager, Reservation, Signal, UserEvent } from "./types"
import { FatalError, TimeoutError, ConnectionError, CacheConflictError, isDetailHttpErrorResponse, NoCacheEntryError } from "./types"
import { getCachedResultCachedCachedIdGet, type CacheEntry } from "@/client";


function withTimeout<T>(promise : Promise<T>, timeoutMs : number) : Promise<T> {
    return new Promise((resolve, reject) => {
        const timeoutId = setTimeout(() => {
            reject(new TimeoutError(`Request timed out after ${timeoutMs} ms`))
        }, timeoutMs)
        promise.then((result) => {
            clearTimeout(timeoutId)
            resolve(result)
        }).catch((err) => {
            clearTimeout(timeoutId)
            reject(err)
        })
    })
}

function getReservationList(request : KeyedRequestEvent) : Reservation[] {
    if (request.reservationRequest.wait) {
        return request.reservationRequest.reserveList.call()
    }
    else {
        return request.reservationRequest.reserveList
    }
}

/**
 * Below is a brief outline of the behaviour of the request manager.
 * 
 * Each request stored in the request manager can be in one of the following three states:
 * - queued: the request is waiting to be sent/has not been sent yet
 * - unknown: the request has been sent, but we do not yet know the status of the request on the server
 * - retry: the request has been sent and we know it failed due to a recoverable error (e.g. cache conflict), and it is waiting to be retried
 * 
 * Note that there are two methods to send requests to the server: send an actual request, or send a status query on a request. The former is used for requests in the queued/retry states, while the latter is used for requests in the unknown state.
 * 
 * Upon request success, the request is removed from the control of the request manager. For convenience we denote this state by resolved.
 * Upon an unrecoverable failure, the request manager will populate the errors state using the injected setErrors function. The controller will then decide what to do with the failed requests (most likely force a reload). For convenience we denote this state by failed.
 * 
 * We separate errors into 3 categories:
 * - Timeout errors - errors where we send an HTTP request but do not receive a response. Can occur due to connection issues or network latency
 * - Cache errors - errors where we receive a cache conflict response from the server (i.e. request key already in use) or a no cache entry response from the server.
 * - Fatal error - everything else (i.e. sent to backend and received some bad data response)
 * 
 * Requests can transition according to the following rules:
 * 
 * - any state -> success: when the request is sent and we receive a success response from the server
 * - any state -> failure: when the request is sent and we receive a fatal error response from the server
 * - any state -> unknown: when the request is sent and we receive a timeout error
 * - any state -> retry: when the request is sent and we receive a cache conflict error or a no cache entry error
 * 
 * For each request event we keep track of a request key and a retry count. This applies to each of the states above. Each event is sent to the server along with its request key.
 * Each time a request is sent to the server, its retry count decreases. If the retry count hits <0, the request is considered failed and will transition to the failed state.
 * Whenever a request transitions to the retry state, its request key will be regenerated.
 * 
 * Below is the general execution flow.
 * 
 * 1. User events are placed into a queue of events.
 * 2. Upon certain event triggers (e.g. after a debounce period with no new events), the request manager selects new events to be sent to the server according to the following algorithm:
 *      From queued state:
 *      - while the request queue is nonempty and the front request in the queue is reserveable (see IdRepository for what reserveable means):
 *          - remove the front request from the queue and place it into a list of outgoing requests
 *          - reserve the provisional ids corresponding to the event
 *      If any event from the unknown/retry states has retry count <0, immediately throw a fatal error. 
 *      For each unknown event, ping the server for the status of the request using the request key.
 *      For each retry event, send a full request.
 * 3. Aggregate all events and sent them to the server along with their request keys.
 * 4. Receive the responses/errors from all the events and do the following:
 *      - For each successful event (no matter which state), free the corresponding provisional ids corresponding to that request event.
 *      - For each failed event (no matter which state)
 *          - Decrement the corresponding retry count.
 *          - If the error was a cache conflict, regenerate the request key.
 *          - Move the event to the corresponding state.
 *         - Continue holding the provisional ids for the event.
 * 5. Repeat steps 1-4 until there are no more recorded request events left.
 * 
 * Notes:
 * - The only edge case the author can think of at the moment is if a request is sent and received by the server, a cache conflict occurs, but the response from the server is lost due to connection issues. In this case, the request manager will place the request in the unknown state instead of the retry state. When the request manager pings the server about the status, it will see another request with the same key that has succeeded, when it should have retried the request. This leaves the frontend in an inconsistent state (if an error response was received instead, the frontend will see a fatal error and refresh). However, this is a very unlikely noncritical edge case and we will put off fixing it for now. Furthermore, we can mitigate this issue by making the request keys more collision resistant.
 */

export function buildRequestManager(idRepo : IDRepository, setErrors : (errors : Error[] | null) => void) : RequestManager {
    const requestQueue : KeyedRequestEvent[] = []
    let statusQueries : CachedKeyedRequestEvent[] = [] // requests for which we have sent the main request and are now polling for their status
    let retryRequests : KeyedRequestEvent[] = [] // requests that have failed due to cache conflicts/known recoverable errors and should be retried
    let userEventTimeout : ReturnType<typeof setTimeout> | null = null
    let debounceLock : boolean = false // if true do not send any requests to server
    let requestLoopRunning : boolean = false

    const isQueueEmpty = () => requestQueue.length === 0 && statusQueries.length === 0 && retryRequests.length === 0

    const enqueueRequest = (request : RequestEvent) => {
        requestQueue.push({ ...request, requestKey: crypto.randomUUID(), retries: 3 })
    }

    let controllerSignalHandler : (signal : Signal) => void = () => {}

    const passSignal = (signal : Signal) => {
        controllerSignalHandler(signal)
    }

    const attachControllerSignalHandler = (handler : (signal : Signal) => void) => {
        controllerSignalHandler = handler
    }

    const handleSignal = () => {
        return
    }

    const requestStatusQueries = () : Promise<CacheEntry>[] => {
        return statusQueries.map((request) => withTimeout(new Promise<CacheEntry>((resolve, reject) => {
            getCachedResultCachedCachedIdGet({
                path: {
                    cachedId: request.requestKey
                }
            }).catch((err) => {
                reject(new ConnectionError(`Failed to fetch status for request ${request.requestKey}`, err))
            }).then((response) => {
                if (!response) {
                    reject(new FatalError(`No response received while fetching status for request ${request.requestKey}`))
                    return
                }
                if (response.error) {
                    if (isDetailHttpErrorResponse(response.error)) {
                        reject(new NoCacheEntryError(`No cache entry found for request ${request.requestKey}`, request.requestKey))
                    }
                    else {
                        reject(new FatalError(`Unexpected error response while fetching status for request ${request.requestKey}: ${JSON.stringify(response.error)}`))
                    }
                }
                else {
                    resolve(response.data)
                }
            })
         }), 10000))
    }


    const send = async () => {
        const fromQueueRequests = []

        let delay : number | null = 1000 // todo: implement exponential backoff for retries instead of fixed delay
        if (statusQueries.some((request) => request.retries < 0) || retryRequests.some((request) => request.retries < 0)) {
            ((statusQueries as KeyedRequestEvent[]).concat(retryRequests)).filter((request) => request.retries < 0).forEach((request) => { 
                getReservationList(request).forEach((reservation) => idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id))
                request.onFailure?.()
            })
            throw new FatalError("A request has exceeded the maximum number of retries")
        }
        while (
            requestQueue.length > 0 
            && !requestQueue[0].reservationRequest.wait?.()
            && (
                requestQueue[0].reservationRequest.skip?.() 
                || getReservationList(requestQueue[0]).every((reservation) => idRepo.isReserveable(reservation.kind, reservation.id, reservation.desiredState))
            )
        )
        {
            const request = requestQueue.shift()!
            if (request.reservationRequest.skip?.()) {
                continue
            }
            const reservationRequest = request.reservationRequest
            if (reservationRequest.wait) {
                reservationRequest.reserveList.call().forEach((reservation) => idRepo.reserveIdObjState(reservation.kind, reservation.id, reservation.desiredState))
            }
            else {
                reservationRequest.reserveList.forEach((reservation) => idRepo.reserveIdObjState(reservation.kind, reservation.id, reservation.desiredState))
            }
            fromQueueRequests.push(request)
        }
        
        const statusQueryPromises = requestStatusQueries()

        const newStatusQueries : CachedKeyedRequestEvent[] = []
        const newRetryRequests : KeyedRequestEvent[] = []
        const [fromQueueResult, statusQueryResult, retryResult] = await Promise.allSettled([
            Promise.allSettled(fromQueueRequests.map((request) => withTimeout(request.callback(request.requestKey), 10000))),
            Promise.allSettled(statusQueryPromises),
            Promise.allSettled(retryRequests.map((request) => withTimeout(request.callback(request.requestKey), 10000))),
        ])

        if (fromQueueResult.status === "rejected") {
            throw new FatalError("Error occured in queue requests: how the hell did that happen?", fromQueueResult.reason instanceof Error ? fromQueueResult.reason : new Error(String(fromQueueResult.reason)))            
        }
        if (statusQueryResult.status === "rejected") {
            throw new FatalError("Error occured in status query requests: how the hell did that happen?", statusQueryResult.reason instanceof Error ? statusQueryResult.reason : new Error(String(statusQueryResult.reason)))            
        }
        if (retryResult.status === "rejected") {
            throw new FatalError("Error occured in retry requests: how the hell did that happen?", retryResult.reason instanceof Error ? retryResult.reason : new Error(String(retryResult.reason)))            
        }
        const errorsList = []
        for (let i = 0; i < fromQueueResult.value.length; i++) {
            const result = fromQueueResult.value[i]
            const request = fromQueueRequests[i]
            if (result.status === "rejected") {
                if (result.reason instanceof TimeoutError || result.reason instanceof ConnectionError) {
                    if (request.handleCachedResult) {
                        newStatusQueries.push({ ...request, retries: request.retries - 1})
                    }
                    else {
                        newRetryRequests.push({ ...request, retries: request.retries - 1, requestKey: crypto.randomUUID()})
                    }
                }
                else if (result.reason instanceof CacheConflictError) {
                    newRetryRequests.push({ ...request, retries: request.retries - 1, requestKey: crypto.randomUUID()})
                }
                else {
                    errorsList.push({request: request, reason: result.reason})
                    getReservationList(request).forEach((reservation) => idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id))
                    request.onFatalError?.(result.reason)
                }
            }
            else {
                getReservationList(request).forEach((reservation) => idRepo.releaseIdObjStateOnSuccess(reservation.kind, reservation.id))
                passSignal(result.value)
                delay = null
            }
        }
        for (let i = 0; i < statusQueryResult.value.length; i++) {
            const result = statusQueryResult.value[i]
            const request = statusQueries[i]
            if (result.status === "rejected") {
                if (result.reason instanceof TimeoutError || result.reason instanceof ConnectionError) {
                    newStatusQueries.push({ ...request, retries: request.retries - 1})
                }
                else if (result.reason instanceof NoCacheEntryError) {
                    newRetryRequests.push({ ...request, retries: request.retries - 1, requestKey: crypto.randomUUID()})
                }
                else {
                    errorsList.push({request: request, reason: result.reason})
                    getReservationList(request).forEach((reservation) => idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id))
                    request.onFatalError?.(result.reason)
                }
            }
            else {
                try {
                    const { signal, status, error } = request.handleCachedResult(result.value, request.requestKey)
                    if (status === "success") {
                        getReservationList(request).forEach((reservation) => idRepo.releaseIdObjStateOnSuccess(reservation.kind, reservation.id))
                        passSignal(signal)
                        delay = null
                    }
                    else if (status === "pending") {
                        newStatusQueries.push({ ...request, retries: request.retries - 1})
                    }
                    else {
                        if (error instanceof CacheConflictError || error instanceof NoCacheEntryError) {
                            newRetryRequests.push({ ...request, retries: request.retries - 1, requestKey: crypto.randomUUID()})
                        }
                        else {
                            errorsList.push({request: request, reason: error})
                            getReservationList(request).forEach((reservation) => idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id))
                            request.onFatalError?.(error)
                        }
                    }
                } catch (err) {
                    errorsList.push({request: request, reason: err instanceof Error ? err : new Error(String(err))})
                    getReservationList(request).forEach((reservation) => idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id))
                    request.onFatalError?.(err instanceof Error ? err : new Error(String(err)))
                }
            }
        }
        for (let i = 0; i < retryResult.value.length; i++) {
            const result = retryResult.value[i]
            const request = retryRequests[i]
            if (result.status === "rejected") {
                if (result.reason instanceof TimeoutError || result.reason instanceof ConnectionError) {
                    if (request.handleCachedResult) {
                        newStatusQueries.push({ ...request, retries: request.retries - 1})
                    }
                    else {
                        newRetryRequests.push({ ...request, retries: request.retries - 1, requestKey: crypto.randomUUID()})
                    }
                }
                else if (result.reason instanceof CacheConflictError) {
                    newRetryRequests.push({ ...request, retries: request.retries - 1, requestKey: crypto.randomUUID()})
                }
                else {
                    errorsList.push({request: request, reason: result.reason})
                    getReservationList(request).forEach((reservation) => idRepo.releaseIdObjStateOnFailure(reservation.kind, reservation.id))
                    request.onFatalError?.(result.reason)
                }
            }
            else {
                getReservationList(request).forEach((reservation) => idRepo.releaseIdObjStateOnSuccess(reservation.kind, reservation.id))
                passSignal(result.value)
                delay = null
            }
        }
        if (errorsList.length > 0) {
            setErrors(errorsList.map((error) => new Error(`Request with key ${error.request.requestKey} failed: ${error.reason instanceof Error ? error.reason.message : String(error.reason)}`, error.reason instanceof Error ? error.reason : new Error(String(error.reason)))))
        }
        else {
            setErrors(null)
        }
        statusQueries = newStatusQueries
        retryRequests = newRetryRequests
        
        return delay
    }

    const start = async () => {
        if (requestLoopRunning) {
            return
        }
        requestLoopRunning = true

        try {
            while(!isQueueEmpty()) {
                if (debounceLock) {
                    await new Promise((resolve) => {
                        setTimeout(resolve, 100)
                    })
                }
                else {
                    const delay = await send()
                    if (delay) {
                        await new Promise((resolve) => {
                            setTimeout(resolve, delay)
                        })
                    }
                }
            }
        } catch (err) {
            console.error("Error occurred in request loop:", err)
            if (err instanceof FatalError) {
                setErrors([err])
            }
            else if (err instanceof TimeoutError || err instanceof ConnectionError) {
                setErrors([err])
            }
            else {
                setErrors([new Error("Unexpected error occurred in request loop", err instanceof Error ? err : new Error(String(err)))])
            }
        } finally {
            requestLoopRunning = false
        }
    }

    const onUserEvent = (event : UserEvent) => {
        console.log("User event:", event)
        if (["textOp", "labelOp", "addLabelGroup", "loadGroup", "switchMode"].includes(event.eventType)) {
            debounceLock = true
            if (userEventTimeout) {
                clearTimeout(userEventTimeout)
            }
            userEventTimeout = setTimeout(() => {
                userEventTimeout = null
                debounceLock = false
            }, 1000)
            if (!requestLoopRunning) {
                start()
            }
        }
    }

    return {
        isQueueEmpty,
        enqueueRequest,
        handleSignal,
        onUserEvent,
        send,
        start,
        attachControllerSignalHandler
    }
}
