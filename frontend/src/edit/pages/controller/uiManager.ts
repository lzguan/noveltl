import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import type { DecoratedSignal, MyStyle, ProvisionalId, UIManager } from "./types";
import { makeBasicSegmentManager, type ManagedLabel } from "@/components/labeled-text-lib/core/segmentManager";

export function buildUIManager(initialText : string, initialLabels : ManagedLabel<MyStyle, StyledLabel<MyStyle>>[]) : UIManager {
    const segmentManager = makeBasicSegmentManager(initialText, initialLabels)


    const handleSignal = (signal : DecoratedSignal) => {
        if (signal?.type === "groupLoaded") {
            segmentManager.batch(() => {
                const labels = signal.getLabels()
                labels.forEach((label) => {
                    segmentManager.addLabel(label.labelId, {
                        interval: { start: label.labelStart, end: label.labelEnd },
                        style: [
                            { color: signal.color },
                            { visible: signal.visible, mutable: signal.mutable, cursorStatus: "none", active: false }
                        ]
                    })
                })
            })
        }
        else if (signal?.type === "clearLabels") {
            segmentManager.batch(() => {
                signal.labelIds.forEach((labelId) => {
                    segmentManager.removeLabel(labelId)
                })
            })
        }
        else if (signal?.type === "detachedIds") {
            segmentManager.batch(() => {
                signal.detachedIds.forEach((detachedId) => {
                    if (detachedId.kind === "label") {
                        segmentManager.removeLabel(detachedId.id)
                    }
                })
            })
        }
    }

    const toggleVisibility = (labelIds: ProvisionalId[], visible: boolean) => {
        segmentManager.batch(() => {
            labelIds.forEach((labelId) => {
                const label = segmentManager.getLabel(labelId)
                segmentManager.updateLabel(labelId, {
                    style: [
                        { ...label.style[0] },
                        { ...label.style[1], visible }
                    ],
                    interval: label.interval
                })
            })
        })
    }

    const toggleClickStatus = (labelIds: ProvisionalId[], clickStatus: "clicked" | "none") => {
        segmentManager.batch(() => {
            labelIds.forEach((labelId) => {
                const label = segmentManager.getLabel(labelId)
                segmentManager.updateLabel(labelId, {
                    style: [
                        { ...label.style[0] },
                        { ...label.style[1], cursorStatus: clickStatus }
                    ],
                    interval: label.interval
                })
            })
        })
    }

    const toggleActiveStatus = (labelIds: ProvisionalId[], active: boolean) => {
        segmentManager.batch(() => {
            labelIds.forEach((labelId) => {
                const label = segmentManager.getLabel(labelId)
                segmentManager.updateLabel(labelId, {
                    style: [
                        { ...label.style[0] },
                        { ...label.style[1], active }
                    ],
                    interval: label.interval
                })
            })
        })
    }

    const toggleHoverStatus = (labelIds: ProvisionalId[], hover: "hovered" | "none") => {
        segmentManager.batch(() => {
            labelIds.forEach((labelId) => {
                const label = segmentManager.getLabel(labelId)
                segmentManager.updateLabel(labelId, {
                    style: [
                        { ...label.style[0] },
                        { ...label.style[1], cursorStatus: label.style[1].cursorStatus === "clicked" ? "clicked" : hover }
                    ],
                    interval: label.interval
                })
            })
        })
    }

    return {
        segmentManager,
        handleSignal,
        toggleVisibility,
        toggleClickStatus,
        toggleActiveStatus,
        toggleHoverStatus
    }
}
