import { useRef, useState } from "react";
import { type Controller, type DataManager, type ProvisionalId, type RequestManager, type Signal, type UIManager, type UserEvent } from "./types";
import { type EditChapterData } from "@/client";
import type { Color } from "@/components/labeled-text-lib/builtin/colors";


export function useController( editChapterData : EditChapterData, getMode: () => "edit" | "label" | "view", setMode: (mode: "edit" | "label" | "view") => void, { requestManager, dataManager, colourMapping, uiManager} : { requestManager: RequestManager; dataManager: DataManager; colourMapping: Map<ProvisionalId, Color>; uiManager: UIManager }, setErrors : (e : Error[] | null) => void): Controller {
    
    const [activeLabelGroupId, setActiveLabelGroupId] = useState<ProvisionalId | null>(null)

    
    const clickedLabelIdsRef = useRef<ProvisionalId[]>([])
    const hoveredLabelIdsRef = useRef<ProvisionalId[]>([])

    const queueStatus = useRef<"none" | "labelOps" | "textOps">("none")

    const handleTextOpEvent = (event : UserEvent) => {
        if (event.eventType !== "textOp") {
            throw new Error("handleTextOpEvent called with non-textOp event")
        }
        if (getMode() !== "edit") {
            setErrors([new Error("Received text operation event while not in edit mode")])
        } else {
            if (queueStatus.current === "labelOps") {
                const requestEvents = dataManager.flushLabelOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
            }
            queueStatus.current = "textOps"
            if (event.op.op === "insert") {
                try {
                    dataManager.insertTextAt(event.op.start, event.op.text)
                    uiManager.insertTextAt(event.op.start, event.op.text)
                } catch (err) {
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
            else if (event.op.op === "delete") {
                try {
                    dataManager.deleteTextAt(event.op.start, event.op.text.length)
                    uiManager.deleteTextAt(event.op.start, event.op.text.length)
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
        } else {
            if (queueStatus.current === "textOps") {
                const requestEvents = dataManager.flushTextOps()
                requestEvents.forEach((requestEvent) => requestManager.enqueueRequest(requestEvent))
            }
            queueStatus.current = "labelOps"
            if (event.op.op === "add") {
                try {
                    const labelDataId = dataManager.getEntries().find((entry) => entry.labelGroup.labelGroupId === event.labelGroupId)?.labelData.labelDataId
                    if (!labelDataId) {
                        throw new Error(`Label data not found for label group ID ${event.labelGroupId}`)
                    }
                    const provisionalLabelId = dataManager.addLabel(
                        event.labelGroupId, 
                        labelDataId,
                        event.op.startPos,
                        event.op.endPos,
                        event.op.word,
                        event.op.entityGroup || undefined,
                        event.op.score,
                        event.op.dirty
                    )
                    uiManager.addLabel(provisionalLabelId, {
                        style: [
                            { color: colourMapping.get(event.labelGroupId)! }, { 
                                visible: true, 
                                mutable: (() => {
                                    const role = dataManager.getEntries().find((entry) => entry.labelGroup.labelGroupId === event.labelGroupId)!.role
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
                    const labelDataId = dataManager.getEntries().find((entry) => entry.labelGroup.labelGroupId === event.labelGroupId)?.labelData.labelDataId
                    if (!labelDataId) {
                        throw new Error(`Label data not found for label group ID ${event.labelGroupId}`)
                    }
                    const labelId = dataManager.deleteLabel(
                        event.labelGroupId,
                        labelDataId,
                        event.op.startPos,
                        event.op.endPos
                    )
                    uiManager.removeLabel(labelId)
                } catch (err) {
                    setErrors([err instanceof Error ? err : new Error(String(err))])
                }
            }
            else {
                try {
                    const labelDataId = dataManager.getEntries().find((entry) => entry.labelGroup.labelGroupId === event.labelGroupId)?.labelData.labelDataId
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
                        event.op.entityGroup || undefined,
                        event.op.score || undefined,
                        event.op.dirty || undefined
                    )
                    uiManager.updateLabel(labelId, {
                        style: [
                            { 
                                color: colourMapping.get(event.labelGroupId)! 
                            }, 
                            { 
                                visible: true, 
                                mutable: (() => {
                                    const role = dataManager.getEntries().find((entry) => entry.labelGroup.labelGroupId === event.labelGroupId)!.role
                                    return role === "editor" || role === "owner"
                                })(),
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
            colourMapping.set(provisionalLabelGroupId, Math.floor(Math.random() * 16777215))
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
                const curEntry = dataManager.getEntries().find((entry) => entry.labelGroup.labelGroupId === activeLabelGroupId)
                curEntry?.labels.forEach((label) => { 
                    const lab = uiManager.getLabel(label.labelId)
                    uiManager.updateLabel(label.labelId, {
                        interval: lab.interval,
                        style: [
                            {
                                ...lab.style[0]
                            },
                            {
                                ...lab.style[1],
                                active: false
                            }
                        ]
                    })
                })
                const newEntry = dataManager.getEntries().find((entry) => entry.labelGroup.labelGroupId === event.labelGroupId)
                newEntry?.labels.forEach((label) => { 
                    const lab = uiManager.getLabel(label.labelId)
                    uiManager.updateLabel(label.labelId, {
                        interval: lab.interval,
                        style: [
                            {
                                ...lab.style[0]
                            },
                            {
                                ...lab.style[1],
                                active: true
                            }
                        ]
                    })
                })
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
                const newClickedLabelIds = dataManager.getEntries().flatMap((entry) => entry.labels.filter((label) => label.labelStart <= pos && label.labelEnd > pos).map((label) => label.labelId))

                uiManager.batch(() => {
                    clickedLabelIds.forEach((labelId) => {
                        const lab = uiManager.getLabel(labelId)
                        uiManager.updateLabel(labelId, {
                            interval: lab.interval,
                            style: [
                                {
                                    ...lab.style[0]
                                },
                                {
                                    ...lab.style[1],
                                    cursorStatus: "none"
                                }
                            ]
                        })
                    })
                    newClickedLabelIds.forEach((labelId) => {
                        const lab = uiManager.getLabel(labelId)
                        uiManager.updateLabel(labelId, {
                            interval: lab.interval,
                            style: [
                                {
                                    ...lab.style[0]
                                },
                                {
                                    ...lab.style[1],
                                    cursorStatus: "clicked"
                                }
                            ]
                        })
                    })
                })
                clickedLabelIdsRef.current = newClickedLabelIds
            }
            else {
                uiManager.batch(() => {
                    clickedLabelIds.forEach((labelId) => {
                        const lab = uiManager.getLabel(labelId)
                        uiManager.updateLabel(labelId, {
                            interval: lab.interval,
                            style: [
                                {
                                    ...lab.style[0]
                                },
                                {
                                    ...lab.style[1],
                                    cursorStatus: "none"
                                }
                            ]
                        })
                    })
                })
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
                const newHoveredLabelIds = dataManager.getEntries().flatMap((entry) => entry.labels.filter((label) => label.labelStart <= pos && label.labelEnd > pos).map((label) => label.labelId))

                uiManager.batch(() => {
                    hoveredLabelIds.forEach((labelId) => {
                        const lab = uiManager.getLabel(labelId)
                        uiManager.updateLabel(labelId, {
                            interval: lab.interval,
                            style: [
                                {
                                    ...lab.style[0]
                                },
                                {
                                    ...lab.style[1],
                                    cursorStatus: lab.style[1].cursorStatus === "clicked" ? "clicked" : "none"
                                }
                            ]
                        })
                    })
                    newHoveredLabelIds.forEach((labelId) => {
                        const lab = uiManager.getLabel(labelId)
                        uiManager.updateLabel(labelId, {
                            interval: lab.interval,
                            style: [
                                {
                                    ...lab.style[0]
                                },
                                {
                                    ...lab.style[1],
                                    cursorStatus: lab.style[1].cursorStatus === "clicked" ? "clicked" : "hovered"
                                }
                            ]
                        })
                    })
                })
                hoveredLabelIdsRef.current = newHoveredLabelIds
            }
            else {
                uiManager.batch(() => {
                    hoveredLabelIds.forEach((labelId) => {
                        const lab = uiManager.getLabel(labelId)
                        uiManager.updateLabel(labelId, {
                            interval: lab.interval,
                            style: [
                                {
                                    ...lab.style[0]
                                },
                                {
                                    ...lab.style[1],
                                    cursorStatus: lab.style[1].cursorStatus === "clicked" ? "clicked" : "none"
                                }
                            ]
                        })
                    })
                })
                hoveredLabelIdsRef.current = []
            }
        } catch (err) {
            setErrors([err instanceof Error ? err : new Error(String(err))])
        }
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
        requestManager.onUserEvent(event)
    }

    const handleSignal = (signal : Signal) => {
        requestManager.handleSignal(signal)
        dataManager.handleSignal(signal)
    }

    return {
        handleEvent,
        uiManager,
        handleSignal
    }
}