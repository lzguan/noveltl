import { createLabelGroupLabelGroupsPost, type AddLabelOp, type DeleteLabelOp, type EditChapterData, type Label, type LabelData, type LabelGroup, type Role, type TextOp, type UpdateLabelOp } from "@/client";
import type { ColorStyle, ProductStyle } from "@/components/labeled-text-lib/builtin/reducers";
import type { SegmentManager } from "@/components/labeled-text-lib/core/segmentManager";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import { useRef, useState } from "react";

type MyStyle = ProductStyle<[ColorStyle, { visible: boolean, mutable: boolean }]>

type LabelOp = AddLabelOp | DeleteLabelOp | UpdateLabelOp

/**
 * Event types that (might) affect the text/labels or the UI state of the editor, which need to be processed by the controller.
 */
type UserEvent = { _type : "textOp", op : TextOp } // text op 
| { eventType : "labelOp", op : LabelOp, labelGroupId : string } // label op
| { eventType : "addLabelGroup", labelGroupName : string } // add a new label group
| { eventType : "switchMode", mode : "edit" | "label" | "view" } // switch between text editing mode, label editing mode and view mode (no editing)
| { eventType : "switchLabelGroup", labelGroupId : string | null } // place focus on a specific label group
| { eventType : "hoverPos", pos : number | null } // hover on a specific position in text, or null to clear hover
| { eventType : "clickPos", pos : number | null } // click on a specific position in text, or null to clear click

type Signal = null | { signalType : "changeLabelGroupId", oldId : string, newId : string }

type RequestEvent = { request : () => Promise<Signal>, requestType : "addLabelGroup" | "textOp" | "labelOp" } // an event that requires async operations, such as fetching data from server or saving data to server. The controller will execute the function and handle the loading/error state.


type Entry = {
    labelGroup : LabelGroup & { provisional: boolean } // whether the label group is provisional (not saved to server yet)
    labelData : LabelData & { provisional: boolean } | null // whether the label data is provisional (not saved to server yet)
    labels : Label[] // sorted by start position
    role : Role
    visible : boolean
}

type DataManager = {
    text : string
    entries : Entry[]
    chapterContentId : string | null

    addLabelGroup : (labelGroupName : string) => RequestEvent
    addLabel : (labelGroupId : string, labelDataId : string, startPos : number, endPos : number, word : string) => RequestEvent
    deleteLabel : (labelGroupId : string, labelDataId : string, startPos : number, endPos : number) => RequestEvent
    updateLabel : (labelGroupId : string, labelDataId : string, startPos : number, endPos : number, newStartPos? : number | null, newEndPos? : number | null, newWord? : string | null) => RequestEvent
    insertTextAt : (pos : number, text : string) => RequestEvent
    deleteTextAt : (startPos : number, endPos : number) => RequestEvent

    handleSignal : (signal : Signal) => void
}

type RequestManager = {
    isQueueEmpty : boolean
    error : unknown | null
    enqueueRequest : (request : RequestEvent) => void

    handleSignal : (signal : Signal) => void
}

export interface Controller {
    handleEvent : (event : UserEvent) => void
    uiManager : SegmentManager<MyStyle, StyledLabel<MyStyle>>
    requestManager : RequestManager
    dataManager : DataManager
    error : unknown

    handleSignal : (signal : Signal) => void
}

function useDataManager(editChapterData : EditChapterData | null, novelId : string, chapterId : string) : DataManager {
    // things that exist locally but not on the server (e.g. added label groups)
    const provisionalGroupIdsRef = useRef<Set<string>>(new Set())
    
    // things that exist on the server but not locally (e.g. deleted label groups)
    const deletedGroupIdsRef = useRef<Set<string>>(new Set()) 

    // actual stuff
    const [text, setText] = useState(editChapterData ?  editChapterData.chapterContent.chapterContentText : "")
    const [chapterContentId, setChapterContentId] = useState(editChapterData ? editChapterData.chapterContent.chapterContentId : null)
    const tempEntries : Entry[] = []
    if (editChapterData) {
        for (const labelGroupListEntry of editChapterData.labelGroupList) {
            tempEntries.push({
                labelGroup: { ...labelGroupListEntry.labelGroup, provisional: false },
                labelData: labelGroupListEntry.labelData ? { ...labelGroupListEntry.labelData, provisional: false } : null,
                labels: [],
                role: labelGroupListEntry.role,
                visible: false
            })
        }
        for (const labelDataListEntry of editChapterData.labelDataList) {
            const entry = tempEntries.find((entry) => entry.labelData?.labelDataId === labelDataListEntry.labelDataId)
            if (entry) {
                entry.labels = labelDataListEntry.labels.sort((a, b) => a.labelStart - b.labelStart)
                entry.visible = true
            }
        }
    }
    const [entries, setEntries] = useState<Entry[]>(tempEntries)

    const addLabelGroup = (labelGroupName : string) : RequestEvent => {
        const newEntries = [...entries]
        const provisionalId = `provisional-${Date.now()}`
        newEntries.unshift({
            labelGroup: { labelGroupId: provisionalId, labelGroupName, novelId, provisional: true },
            labelData: null,
            labels: [],
            role: "owner",
            visible: true,
        })
        setEntries(newEntries)
        provisionalGroupIdsRef.current.add(provisionalId)

        return { 
            request : async () => {
                return await createLabelGroupLabelGroupsPost({ body: { novelId, labelGroupName}}).then((newLabelGroup) => {
                    const newNewEntries = [...entries]
                    const curEntry = newNewEntries.find((entry) => entry.labelGroup.labelGroupId === provisionalId)
                    if (!curEntry) {
                        return { signalType: "changeLabelGroupId", oldId: provisionalId, newId: newLabelGroup.labelGroupId } as Signal
                    }
                    curEntry.labelGroup = { ...newLabelGroup, provisional: false }
                    setEntries(newNewEntries)
                    provisionalGroupIdsRef.current.delete(provisionalId)
                    return { signalType: "changeLabelGroupId", oldId: provisionalId, newId: newLabelGroup.labelGroupId } as Signal
                })
            },
            requestType: "addLabelGroup"
        }
    }

    const addLabel = (labelGroupId : string, labelDataId : string, startPos : number, endPos : number, word : string) : RequestEvent => {

    }
}