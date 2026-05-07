import { useCallback, useEffect, useRef, useState } from "react";
import { makeDecoratedSignal, type Controller, type DecoratedSignal, type LabelGroupView, type ProvisionalId, type Runtime, type Signal, type UserEvent } from "./types";
import { type EditChapterData } from "@/client";
import { generateRandomColor } from "@/components/labeled-text-lib/builtin/colors";


function buildLabelGroupViews(
    dataManager: Runtime["dataManager"],
    visibilityMapping: Runtime["visibilityMapping"],
    colorMapping: Runtime["colorMapping"]
): LabelGroupView[] {
    return dataManager.getGroups().map((group) : LabelGroupView => ({
        labelGroupId: group.labelGroupId,
        labelGroupName: dataManager.getForGroup.name(group.labelGroupId),
        role: dataManager.getForGroup.role(group.labelGroupId),
        loadingStatus: dataManager.getForGroup.loadingStatus(group.labelGroupId),
        visible: visibilityMapping.get(group.labelGroupId) ?? false,
        color: colorMapping.get(group.labelGroupId) ?? 0
    }))
}

export function useController( editChapterData : EditChapterData, getMode: () => "edit" | "label" | "view", setMode: (mode: "edit" | "label" | "view") => void, { requestManager, dataManager, colorMapping, uiManager, visibilityMapping } : Runtime, setErrors : (e : Error[] | null) => void): Controller {
    const [activeLabelGroupId, setActiveLabelGroupId] = useState<ProvisionalId | null>(null)
    const [labelGroupViews, setLabelGroupViews] = useState<LabelGroupView[]>(() => buildLabelGroupViews(dataManager, visibilityMapping, colorMapping))

    const syncLabelGroupViews = useCallback(() => {
        setLabelGroupViews(buildLabelGroupViews(dataManager, visibilityMapping, colorMapping))
    }, [dataManager, visibilityMapping, colorMapping])
    useEffect(() => {
        dataManager.attachLabelGroupSyncHandler(syncLabelGroupViews)

        return () => dataManager.attachLabelGroupSyncHandler(() => {}) // detach handler on unmount
    }, [dataManager, syncLabelGroupViews])
    
    const clickedLabelIdsRef = useRef<ProvisionalId[]>([])
    const hoveredLabelIdsRef = useRef<ProvisionalId[]>([])

    const queueStatus = useRef<"none" | "labelOps" | "textOps">("none")

    const handleTextOpEvent = (event : UserEvent) => {
        if (event.eventType !== "textOp") {
            throw new Error("handleTextOpEvent called with non-textOp event")
        }
        if (getMode() !== "edit") {
            setErrors([new Error("Received text operation event while not in edit mode")])
        } 
        else if (editChapterData.role === "viewer") {
            setErrors([new Error("You do not have permission to edit")])
        }
        else {
            if (queueStatus.current === "labelOps") {
                const requestEvents = dataManager.flushLabelOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
            }
            queueStatus.current = "textOps"
            if (event.op.op === "insert") {
                try {
                    dataManager.insertTextAt(event.op.start, event.op.text)
                    uiManager.segmentManager.insertTextAt(event.op.start, event.op.text)
                } catch (err) {
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
            else if (event.op.op === "delete") {
                try {
                    dataManager.deleteTextAt(event.op.start, event.op.text.length)
                    uiManager.segmentManager.deleteTextAt(event.op.start, event.op.text.length)
                } catch (err) {
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
        }
    }

    const handleLabelOpEvent = (event : UserEvent) => {
        if (event.eventType !== "labelOp") {
            throw new Error("handleLabelOpEvent called with non-labelOp event")
        }
        if (getMode() !== "label") {
            setErrors([new Error("Received label operation event while not in label mode")])
        } 
        else if (dataManager.getForGroup.role(event.labelGroupId) === "viewer") {
            setErrors([new Error("You do not have permission to edit labels")])
        }
        else {
            if (queueStatus.current === "textOps") {
                const requestEvents = dataManager.flushTextOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
            }
            queueStatus.current = "labelOps"
            if (event.op.op === "add") {
                try {
                    const labelDataId = dataManager.getForGroup.labelDataId(event.labelGroupId)
                    if (!labelDataId) {
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
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
            else if (event.op.op === "delete") {
                try {
                    const labelDataId = dataManager.getForGroup.labelDataId(event.labelGroupId)
                    if (!labelDataId) {
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
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
            else {
                try {
                    const labelDataId = dataManager.getForGroup.labelDataId(event.labelGroupId)
                    if (!labelDataId) {
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
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
        }
    }

    const handleAddLabelGroupEvent = (event : UserEvent) => {
        if (event.eventType !== "addLabelGroup") {
            throw new Error("handleAddLabelGroupEvent called with non-addLabelGroup event")
        }
        try {
            const [provisionalLabelGroupId, requestEvents] = dataManager.addLabelGroup(event.labelGroupName)
            colorMapping.set(provisionalLabelGroupId, generateRandomColor())
            visibilityMapping.set(provisionalLabelGroupId, false)
            if (queueStatus.current === "textOps") {
                const flushedRequestEvents = dataManager.flushTextOps()
                flushedRequestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus.current = "none"
            }
            else if (queueStatus.current === "labelOps") {
                const flushedRequestEvents = dataManager.flushLabelOps()
                flushedRequestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus.current = "none"
            }
            requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
        } catch (err) {
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
        syncLabelGroupViews()
    }

    const handleSwitchLabelGroupEvent = (event : UserEvent) => {
        if (event.eventType !== "switchLabelGroup") {
            throw new Error("handleSwitchLabelGroupEvent called with non-switchLabelGroup event")
        }
        if (getMode() !== "label") {
            setErrors([new Error("Received switch label group event while not in label mode")])
            return
        }
        try {
            if (event.labelGroupId !== activeLabelGroupId) {
                const activeLabels = activeLabelGroupId !== null ? dataManager.getForGroup.labels(activeLabelGroupId) : []
                uiManager.toggleActiveStatus(activeLabels.map((label) => label.labelId), false)
                const eventLabelIds = event.labelGroupId !== null ? dataManager.getForGroup.labels(event.labelGroupId).map((label) => label.labelId) : []
                uiManager.toggleActiveStatus(eventLabelIds, true)
                setActiveLabelGroupId(event.labelGroupId)
            }
        } catch (err) {
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
    }

    const handleClickPosEvent = (event : UserEvent) => {
        if (event.eventType !== "clickPos") {
            throw new Error("handleClickPosEvent called with non-clickPos event")
        }
        if (getMode() !== "label") {
            setErrors([new Error("Received click position event while not in label mode")])
            return
        }
        try {
            const clickedLabelIds = clickedLabelIdsRef.current
            const pos = event.pos
            if (pos !== null) {
                const newClickedLabelIds = dataManager.getGroups().flatMap((group) => dataManager.getForGroup.labels(group.labelGroupId).filter((label) => label.labelStart <= pos && label.labelEnd > pos).map((label) => label.labelId))

                uiManager.toggleClickStatus(clickedLabelIds, "none")
                uiManager.toggleClickStatus(newClickedLabelIds, "clicked")
                clickedLabelIdsRef.current = newClickedLabelIds
            }
            else {
                uiManager.toggleClickStatus(clickedLabelIds, "none")
                clickedLabelIdsRef.current = []
            }
        } catch (err) {
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
    }

    const handleHoverPosEvent = (event : UserEvent) => {
        if (event.eventType !== "hoverPos") {
            throw new Error("handleHoverPosEvent called with non-hoverPos event")
        }
        if (getMode() !== "label") {
            setErrors([new Error("Received hover position event while not in label mode")])
            return
        }
        try {
            const hoveredLabelIds = hoveredLabelIdsRef.current
            const pos = event.pos
            if (pos !== null) {
                const newHoveredLabelIds = dataManager.getGroups().flatMap((group) => dataManager.getForGroup.labels(group.labelGroupId).filter((label) => label.labelStart <= pos && label.labelEnd > pos).map((label) => label.labelId))
                uiManager.toggleHoverStatus(hoveredLabelIds, "none")
                uiManager.toggleHoverStatus(newHoveredLabelIds, "hovered")
                hoveredLabelIdsRef.current = newHoveredLabelIds
            }
            else {
                uiManager.toggleHoverStatus(hoveredLabelIds, "none")
                hoveredLabelIdsRef.current = []
            }
        } catch (err) {
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
    }

    const handleLoadGroupEvent = (event : UserEvent) => {
        if (event.eventType !== "loadGroup") {
            throw new Error("handleLoadGroupEvent called with non-loadGroup event")
        }
        if (getMode() !== "label") {
            setErrors([new Error("Received load group event while not in label mode")])
            return
        }
        try {
            if (queueStatus.current === "labelOps") {
                const requestEvents = dataManager.flushLabelOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus.current = "none"
            }
            else if (queueStatus.current === "textOps") {
                const requestEvents = dataManager.flushTextOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus.current = "none"
            }
            const requestEvents = dataManager.reloadGroup(event.labelGroupId)
            requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
        } catch (err) {
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
        syncLabelGroupViews()
    }

    const handleToggleVisibilityEvent = (event : UserEvent) => {
        if (event.eventType !== "toggleVisibility") {
            throw new Error("handleToggleVisibilityEvent called with non-toggleVisibility event")
        }
        try {
            const labelIds = dataManager.getForGroup.labels(event.labelGroupId).map((label) => label.labelId)
            uiManager.toggleVisibility(labelIds, event.visible)
            visibilityMapping.set(event.labelGroupId, event.visible)
        } catch (err) {
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
        syncLabelGroupViews()
    }

    const handleSwitchModeEvent = (event : UserEvent) => {
        if (event.eventType !== "switchMode") {
            throw new Error("handleSwitchModeEvent called with non-switchMode event")
        }
        if (event.mode === "edit" && editChapterData.role === "viewer") {
            setErrors([new Error("You do not have permission to switch to edit mode")])
        }
        else {
            if (queueStatus.current === "textOps") {
                const requestEvents = dataManager.flushTextOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus.current = "none"
            }
            else if (queueStatus.current === "labelOps") {
                const requestEvents = dataManager.flushLabelOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus.current = "none"
            }
            setMode(event.mode)
        }
        syncLabelGroupViews()
    }

    const handleEvent = (event : UserEvent) => {
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

    const handleSignal = useCallback((signal : Signal) => {
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
    }, [requestManager, dataManager, uiManager, visibilityMapping, colorMapping, syncLabelGroupViews])

    useEffect(() => {
        requestManager.attachControllerSignalHandler(handleSignal)

        return () => requestManager.attachControllerSignalHandler(() => {}) // detach handler on unmount
    }, [requestManager, handleSignal])

    useEffect(() => {
        const wait = setInterval(() => {
            if (queueStatus.current === "textOps") {
                const requestEvents = dataManager.flushTextOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus.current = "none"
            }
            else if (queueStatus.current === "labelOps") {
                const requestEvents = dataManager.flushLabelOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
                queueStatus.current = "none"
            }
            requestManager.start()
        }, 1500)
        return () => clearInterval(wait)
    }, [dataManager, requestManager, handleSignal])

    return {
        handleEvent,
        uiManager,
        handleSignal,

        labelGroupViews,
        activeLabelGroupId
    }
}
