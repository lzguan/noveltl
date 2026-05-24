import { makeDecoratedSignal, type Controller, type DecoratedSignal, type LabelGroupView, type ProvisionalId, type Runtime, type Signal, type UserEvent } from "./types";
import { type EditChapterData } from "@/client";
import { generateRandomColor } from "@/components/labeled-text-lib/builtin/colors";
import { createLogger } from "@/lib/logging";
import { buildLabelGroupViews } from "./utils";


const logger = createLogger("Controller")

type ControllerState = "initializing" | "running" | "stopping" | "stopped"
type QueueStatus = "none" | "labelOps" | "textOps"

export function buildController(
    editChapterData : EditChapterData,
    getMode: () => "edit" | "label" | "view",
    setMode: (mode: "edit" | "label" | "view") => void,
    { requestManager, dataManager, colorMapping, uiManager, visibilityMapping } : Runtime,
    setErrors : (e : Error[] | null) => void,
    setLabelGroupViews : (views : LabelGroupView[]) => void,
    setActiveLabelGroupId : (id : ProvisionalId | null) => void,
): Controller {
    let activeLabelGroupId :ProvisionalId | null = null
    setLabelGroupViews(buildLabelGroupViews(dataManager, visibilityMapping, colorMapping))

    let state = "initializing" as ControllerState

    const syncLabelGroupViews = () => {
        const views = buildLabelGroupViews(dataManager, visibilityMapping, colorMapping)
        setLabelGroupViews(views)
    }
    dataManager.attachLabelGroupSyncHandler(syncLabelGroupViews)

    let clickedLabelIds : ProvisionalId[] = []
    let hoveredLabelIds : ProvisionalId[] = []

    let queueStatus = "none" as QueueStatus

    const handleTextOpEvent = (event : UserEvent) => {
        if (event.eventType !== "textOp") {
            logger.error("handleTextOpEvent called with non-textOp event", { event })
            throw new Error("handleTextOpEvent called with non-textOp event")
        }
        if (getMode() !== "edit") {
            logger.error("Received text operation event while not in edit mode", { event })
            setErrors([new Error("Received text operation event while not in edit mode")])
        } 
        else if (editChapterData.role === "viewer") {
            logger.error("Failed to perform text operation", { error: new Error("You do not have permission to edit"), event })
            setErrors([new Error("You do not have permission to edit")])
        }
        else {
            if (queueStatus === "labelOps") {
                const requestEvents = dataManager.flushLabelOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
            }
            queueStatus = "textOps"
            if (event.op.op === "insert") {
                try {
                    dataManager.insertTextAt(event.op.start, event.op.text)
                    uiManager.segmentManager.insertTextAt(event.op.start, event.op.text)
                } catch (err) {
                    logger.error("Failed to insert text", { error: err, event })
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
            else if (event.op.op === "delete") {
                try {
                    dataManager.deleteTextAt(event.op.start, event.op.text.length)
                    uiManager.segmentManager.deleteTextAt(event.op.start, event.op.text.length)
                } catch (err) {
                    logger.error("Failed to delete text", { error: err, event })
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
        }
    }

    const handleLabelOpEvent = (event : UserEvent) => {
        if (event.eventType !== "labelOp") {
            logger.error("handleLabelOpEvent called with non-labelOp event", { event })
            throw new Error("handleLabelOpEvent called with non-labelOp event")
        }
        if (getMode() !== "label") {
            logger.error("Received label operation event while not in label mode", { event })
            setErrors([new Error("Received label operation event while not in label mode")])
        } 
        else if (dataManager.getForGroup.role(event.labelGroupId) === "viewer") {
            logger.error("Failed to perform label operation", { error: new Error("You do not have permission to edit labels"), event })
            setErrors([new Error("You do not have permission to edit labels")])
        }
        else {
            if (queueStatus === "textOps") {
                const requestEvents = dataManager.flushTextOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
            }
            queueStatus = "labelOps"
            if (event.op.op === "add") {
                try {
                    const labelDataId = dataManager.getForGroup.labelDataId(event.labelGroupId)
                    if (!labelDataId) {
                        logger.error(`Label data not found for label group ID ${event.labelGroupId} in add label operation`, { event })
                        throw new Error(`Label data not found for label group ID ${event.labelGroupId}`)
                    }
                    const provisionalLabelId = dataManager.addLabel(
                        event.labelGroupId, 
                        labelDataId,
                        event.op.startPos,
                        event.op.endPos,
                        event.op.word,
                        event.op.entityGroup ?? undefined,
                        event.op.score ?? undefined,
                        event.op.dirty ?? undefined
                    )
                    uiManager.segmentManager.addLabel(provisionalLabelId, {
                        style: [
                            { color: colorMapping.get(event.labelGroupId)! }, { 
                                visible: visibilityMapping.get(event.labelGroupId)!, 
                                mutable: (() => {
                                    const role = dataManager.getForGroup.role(event.labelGroupId)
                                    return role === "editor" || role === "owner"
                                })(),
                                cursorStatus: "none",
                                active: event.labelGroupId === activeLabelGroupId
                            }],
                        interval: { start: event.op.startPos, end: event.op.endPos },
                    })
                } catch (err) {
                    logger.error("Failed to add label", { error: err, event })
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
            else if (event.op.op === "delete") {
                try {
                    const labelDataId = dataManager.getForGroup.labelDataId(event.labelGroupId)
                    if (!labelDataId) {
                        logger.error(`Label data not found for label group ID ${event.labelGroupId} in delete label operation`, { event })
                        throw new Error(`Label data not found for label group ID ${event.labelGroupId}`)
                    }
                    const labelId = dataManager.deleteLabel(
                        event.labelGroupId,
                        labelDataId,
                        event.op.startPos,
                        event.op.endPos
                    )
                    uiManager.segmentManager.removeLabel(labelId)
                } catch (err) {
                    logger.error("Failed to delete label", { error: err, event })
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
            else {
                try {
                    const labelDataId = dataManager.getForGroup.labelDataId(event.labelGroupId)
                    if (!labelDataId) {
                        logger.error(`Label data not found for label group ID ${event.labelGroupId} in update label operation`, { event })
                        throw new Error(`Label data not found for label group ID ${event.labelGroupId}`)
                    }
                    const labelId = dataManager.updateLabel(
                        event.labelGroupId,
                        labelDataId,
                        event.op.startPos,
                        event.op.endPos,
                        event.op.newStartPos,
                        event.op.newEndPos,
                        event.op.newWord,
                        event.op.entityGroup ?? undefined,
                        event.op.score ?? undefined,
                        event.op.dirty ?? undefined
                    )
                    uiManager.segmentManager.updateLabel(labelId, {
                        style: [
                            { 
                                color: colorMapping.get(event.labelGroupId)! 
                            }, 
                            { 
                                visible: visibilityMapping.get(event.labelGroupId)!, 
                                mutable: dataManager.getForGroup.role(event.labelGroupId) === "editor" || dataManager.getForGroup.role(event.labelGroupId) === "owner",
                                cursorStatus: "none",
                                active: event.labelGroupId === activeLabelGroupId
                            }
                        ],
                        interval: { start: event.op.newStartPos ?? event.op.startPos, end: event.op.newEndPos ?? event.op.endPos },
                    })
                } catch (err) {
                    logger.error("Failed to update label", { error: err, event })
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
        }
    }

    const handleAddLabelGroupEvent = (event : UserEvent) => {
        if (event.eventType !== "addLabelGroup") {
            logger.error("handleAddLabelGroupEvent called with non-addLabelGroup event", { event })
            throw new Error("handleAddLabelGroupEvent called with non-addLabelGroup event")
        }
        try {
            const [provisionalLabelGroupId, requestEvents] = dataManager.addLabelGroup(event.labelGroupName)
            colorMapping.set(provisionalLabelGroupId, generateRandomColor())
            visibilityMapping.set(provisionalLabelGroupId, false)
            if (queueStatus === "textOps") {
                const flushedRequestEvents = dataManager.flushTextOps()
                flushedRequestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus = "none"
            }
            else if (queueStatus === "labelOps") {
                const flushedRequestEvents = dataManager.flushLabelOps()
                flushedRequestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus = "none"
            }
            requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
        } catch (err) {
            logger.error("Failed to add label group", { error: err, event })
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
        syncLabelGroupViews()
    }

    const handleSwitchLabelGroupEvent = (event : UserEvent) => {
        if (event.eventType !== "switchLabelGroup") {
            logger.error("handleSwitchLabelGroupEvent called with non-switchLabelGroup event", { event })
            throw new Error("handleSwitchLabelGroupEvent called with non-switchLabelGroup event")
        }
        if (getMode() !== "label") {
            logger.error("Received switch label group event while not in label mode", { event })
            setErrors([new Error("Received switch label group event while not in label mode")])
            return
        }
        try {
            if (event.labelGroupId !== activeLabelGroupId) {
                const activeLabels = activeLabelGroupId !== null ? dataManager.getForGroup.labels(activeLabelGroupId) : []
                uiManager.toggleActiveStatus(activeLabels.map((label) => label.labelId), false)
                const eventLabelIds = event.labelGroupId !== null ? dataManager.getForGroup.labels(event.labelGroupId).map((label) => label.labelId) : []
                uiManager.toggleActiveStatus(eventLabelIds, true)
                activeLabelGroupId = event.labelGroupId
                setActiveLabelGroupId(event.labelGroupId)
            }
        } catch (err) {
            logger.error("Failed to switch label group", { error: err, event })
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
    }

    const handleClickPosEvent = (event : UserEvent) => {
        if (event.eventType !== "clickPos") {
            logger.error("handleClickPosEvent called with non-clickPos event", { event })
            throw new Error("handleClickPosEvent called with non-clickPos event")
        }
        if (getMode() !== "label") {
            logger.error("Received click position event while not in label mode", { event })
            setErrors([new Error("Received click position event while not in label mode")])
            return
        }
        try {
            const newClickedLabelIds = clickedLabelIds
            const pos = event.pos
            if (pos !== null) {
                const newClickedLabelIds = dataManager.getGroups().flatMap((group) => dataManager.getForGroup.labels(group.labelGroupId).filter((label) => label.labelStart <= pos && label.labelEnd > pos).map((label) => label.labelId))

                uiManager.toggleClickStatus(newClickedLabelIds, "none")
                uiManager.toggleClickStatus(newClickedLabelIds, "clicked")
                clickedLabelIds = newClickedLabelIds
            }
            else {
                uiManager.toggleClickStatus(newClickedLabelIds, "none")
                clickedLabelIds = []
            }
        } catch (err) {
            logger.error("Failed to click position", { error: err, event })
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
    }

    const handleHoverPosEvent = (event : UserEvent) => {
        if (event.eventType !== "hoverPos") {
            logger.error("handleHoverPosEvent called with non-hoverPos event", { event })
            throw new Error("handleHoverPosEvent called with non-hoverPos event")
        }
        if (getMode() !== "label") {
            logger.error("Received hover position event while not in label mode", { event })
            setErrors([new Error("Received hover position event while not in label mode")])
            return
        }
        try {
            const newHoveredLabelIds = hoveredLabelIds
            const pos = event.pos
            if (pos !== null) {
                const newHoveredLabelIds = dataManager.getGroups().flatMap((group) => dataManager.getForGroup.labels(group.labelGroupId).filter((label) => label.labelStart <= pos && label.labelEnd > pos).map((label) => label.labelId))
                uiManager.toggleHoverStatus(newHoveredLabelIds, "none")
                uiManager.toggleHoverStatus(newHoveredLabelIds, "hovered")
                hoveredLabelIds = newHoveredLabelIds
            }
            else {
                uiManager.toggleHoverStatus(newHoveredLabelIds, "none")
                hoveredLabelIds = []
            }
        } catch (err) {
            logger.error("Failed to hover position", { error: err, event })
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
    }

    const handleLoadGroupEvent = (event : UserEvent) => {
        if (event.eventType !== "loadGroup") {
            logger.error("handleLoadGroupEvent called with non-loadGroup event", { event })
            throw new Error("handleLoadGroupEvent called with non-loadGroup event")
        }
        if (getMode() !== "label") {
            logger.error("Received load group event while not in label mode", { event })
            setErrors([new Error("Received load group event while not in label mode")])
            return
        }
        try {
            if (queueStatus === "labelOps") {
                const requestEvents = dataManager.flushLabelOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus = "none"
            }
            else if (queueStatus === "textOps") {
                const requestEvents = dataManager.flushTextOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus = "none"
            }
            const requestEvents = dataManager.reloadGroup(event.labelGroupId)
            requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
        } catch (err) {
            logger.error("Failed to reload group", { error: err, event })
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
        syncLabelGroupViews()
    }

    const handleToggleVisibilityEvent = (event : UserEvent) => {
        if (event.eventType !== "toggleVisibility") {
            logger.error("handleToggleVisibilityEvent called with non-toggleVisibility event", { event })
            throw new Error("handleToggleVisibilityEvent called with non-toggleVisibility event")
        }
        try {
            const labelIds = dataManager.getForGroup.labels(event.labelGroupId).map((label) => label.labelId)
            uiManager.toggleVisibility(labelIds, event.visible)
            visibilityMapping.set(event.labelGroupId, event.visible)
        } catch (err) {
            logger.error("Failed to toggle visibility", { error: err, event })
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
        syncLabelGroupViews()
    }

    const handleSwitchModeEvent = (event : UserEvent) => {
        if (event.eventType !== "switchMode") {
            logger.error("handleSwitchModeEvent called with non-switchMode event", { event })
            throw new Error("handleSwitchModeEvent called with non-switchMode event")
        }
        if (event.mode === "edit" && editChapterData.role === "viewer") {
            logger.error("Failed to switch mode", { error: new Error("You do not have permission to switch to edit mode"), event })
            setErrors([new Error("You do not have permission to switch to edit mode")])
        }
        else {
            if (queueStatus === "textOps") {
                const requestEvents = dataManager.flushTextOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus = "none"
            }
            else if (queueStatus === "labelOps") {
                const requestEvents = dataManager.flushLabelOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus = "none"
            }
            setMode(event.mode)
        }
        syncLabelGroupViews()
    }

    const handleEvent = (event : UserEvent) => {
        if (state !== "running") {
            logger.info("Received user event while controller is not running, ignoring", { event, state })
            return
        }
        if (event.eventType === "textOp") {
            handleTextOpEvent(event)
        }
        else if (event.eventType === "labelOp") {
            handleLabelOpEvent(event)
        }
        else if (event.eventType === "addLabelGroup") {
            handleAddLabelGroupEvent(event)
        }
        else if (event.eventType === "switchMode") {
            handleSwitchModeEvent(event)
        }
        else if (event.eventType === "switchLabelGroup") {
            handleSwitchLabelGroupEvent(event)
        }
        else if (event.eventType === "clickPos") {
            handleClickPosEvent(event)
        }
        else if (event.eventType === "hoverPos") {
            handleHoverPosEvent(event)
        }
        else if (event.eventType === "loadGroup") {
            handleLoadGroupEvent(event)
        }
        else if (event.eventType === "toggleVisibility") {
            handleToggleVisibilityEvent(event)
        }
        requestManager.onUserEvent(event)
    }

    const handleSignal = (signal : Signal) => {
        let decoratedSignal : DecoratedSignal
        if (signal === null) {
            return
        }
        if (signal.type === "groupLoaded") {
            if (visibilityMapping.get(signal.labelGroupId) === undefined) {
                visibilityMapping.set(signal.labelGroupId, true)
            }
            if (colorMapping.get(signal.labelGroupId) === undefined) {
                colorMapping.set(signal.labelGroupId, generateRandomColor())
            }
            decoratedSignal = makeDecoratedSignal({ ...signal, visible: visibilityMapping.get(signal.labelGroupId)!, color: colorMapping.get(signal.labelGroupId)! })
        }
        else {
            decoratedSignal = makeDecoratedSignal(signal)
        }

        requestManager.handleSignal(decoratedSignal)
        dataManager.handleSignal(decoratedSignal)
        uiManager.handleSignal(decoratedSignal)
        syncLabelGroupViews()
    }

    requestManager.attachControllerSignalHandler(handleSignal)

    let wait : number = 0

    const start = () => {
        state = "running"
        wait = setInterval(() => {
            if (queueStatus === "textOps") {
                const requestEvents = dataManager.flushTextOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus = "none"
            }
            else if (queueStatus === "labelOps") {
                const requestEvents = dataManager.flushLabelOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus = "none"
            }
            void requestManager.start()
        }, 1500)
    }

    const stop = async () => {
        state = "stopping"
        dataManager.detachLabelGroupSyncHandler()
        requestManager.detachControllerSignalHandler()
        clearInterval(wait)
        await requestManager.waitFlush()
        state = "stopped"
    }

    return {
        handleEvent,
        uiManager,
        handleSignal,

        start,
        stop
    }
}
