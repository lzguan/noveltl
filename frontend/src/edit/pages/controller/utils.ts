import { createLabelDataLabelGroupsLabelGroupIdLabelDatasPost, type Chapter, type EditChapterData, type Novel } from "@/client";
import { CacheConflictError, ConnectionError, FatalError, isLabelData, isRequestConflictErrorResponse, validateData, type DataEntry, type IDRepository, type ProvisionalId, type RequestManager, type Runtime } from "./types";
import { buildIdRepository } from "./idRepository";
import { buildRequestManager } from "./requestmanager";
import { buildDataManager } from "./dataManager";
import type { Color } from "@/components/labeled-text-lib/builtin/colors";
import { buildUIManager } from "./uiManager";

export function buildProvisionalChapterContentId(editChapterData: EditChapterData, idRepo : IDRepository) : ProvisionalId {
    return idRepo.newIdAndBindId("chapterContent", editChapterData.chapterContent.chapterContentId)
}

export function buildDataEntries(editChapterData : EditChapterData, idRepo : IDRepository, requestManager : RequestManager, provisionalChapterContentId : ProvisionalId) : DataEntry[] {
    return editChapterData.labelGroupList.map((labelGroupEntry) : DataEntry => { 
        const labelGroupProvisionalId = idRepo.newIdAndBindId("labelGroup", labelGroupEntry.labelGroup.labelGroupId)
        return ({
            labelGroup: { ...labelGroupEntry.labelGroup, labelGroupId: labelGroupProvisionalId, provisional: true },

            labelData: labelGroupEntry.labelData ? { ...labelGroupEntry.labelData, labelDataId: idRepo.newIdAndBindId("labelData", labelGroupEntry.labelData.labelDataId), provisional: true } : (()  => {
                const provisionalId = idRepo.newId("labelData")
                requestManager.enqueueRequest({
                    retries: 3,
                    reserveList: [
                        { kind: "labelGroup", id: labelGroupProvisionalId, desiredState: "locked"},
                        { kind: "labelData", id: provisionalId, desiredState: "creating"},
                        { kind: "chapterContent", id: provisionalChapterContentId, desiredState: "locked"}
                    ],
                    callback: async (requestKey) => {
                        let response
                        try {
                            response = await createLabelDataLabelGroupsLabelGroupIdLabelDatasPost(
                                {
                                    body: {
                                        chapterContentId: idRepo.getServerId("chapterContent", provisionalChapterContentId)!,
                                    },
                                    path: {
                                        labelGroupId: idRepo.getServerId("labelGroup", labelGroupProvisionalId)!
                                    },
                                    query: {
                                        requestKey: requestKey
                                    }
                                }
                            )
                        } catch (err) {
                            throw new ConnectionError("Failed to create label data on server", err instanceof Error ? { cause: err } : undefined)
                        }
                        if (response.error) {
                            if (isRequestConflictErrorResponse(response.error) && response.error.detail.cacheConflict) {
                                throw new CacheConflictError("Request key conflict while creating label data", requestKey)
                            }
                            throw new FatalError(`Server returned an error while creating label data: ${response.error instanceof Error ? response.error.message : String(response.error)}`)
                        }
                        else {
                            idRepo.bindServerId("labelData", provisionalId, response.data.labelDataId)
                        }
                        return null
                    },
                    handleCachedResult: (cachedResult, requestKey) => {
                        if (cachedResult.status === "success") {
                            const validated = validateData(isLabelData, cachedResult.response)
                            idRepo.bindServerId("labelData", provisionalId, validated.labelDataId)
                            return { status: cachedResult.status, signal: null, error : null }
                        }
                        else if (cachedResult.status === "pending") {
                            return { status: cachedResult.status, signal: null, error : null }
                        }
                        else {
                            if (cachedResult.error?.cacheConflict) {
                                return { status: cachedResult.status, signal: null, error : new CacheConflictError("Request key conflict while creating label data", requestKey) }
                            }
                            
                        }
                        return { status: cachedResult.status, signal: null, error : new FatalError("Failed to create label data", cachedResult.error instanceof Error ? cachedResult.error : new Error(String(cachedResult.error))) }
                    },
                    variant: "addLabelData"
                })
                return { labelGroupId: labelGroupProvisionalId, labelDataId: provisionalId, chapterContentId: provisionalChapterContentId, provisional: true }
            })(),

            labels: labelGroupEntry.labelData ? editChapterData.labelDataList.find((labelData) => labelData.labelDataId === labelGroupEntry.labelData!.labelDataId)?.labels.map((label) => ({ ...label, labelId: idRepo.newIdAndBindExists("label"), provisional: true })) || [] : [],

            role: labelGroupEntry.role,
            loadingStatus: editChapterData.labelDataList.some((val) => val.labelDataId === labelGroupEntry.labelData?.labelDataId) ? "loaded" : "notLoaded"
        })
    })
}

export function buildRuntime(setErrors : (errors: Error[] | null) => void, novel : Novel, chapter : Chapter, editChapterData : EditChapterData, userId : string) : Runtime {
        const idRepo = buildIdRepository()
        const requestManager = buildRequestManager(idRepo, setErrors)
        const provisionalChapterContentId = buildProvisionalChapterContentId(editChapterData, idRepo)
        const entries = buildDataEntries(editChapterData, idRepo, requestManager, provisionalChapterContentId)
        const dataManager = buildDataManager(entries, idRepo, novel, chapter, userId, provisionalChapterContentId, editChapterData.chapterContent.chapterContentText)
        const colourMapping = new Map<ProvisionalId, Color>(entries.map((entry) => [entry.labelGroup.labelGroupId, Math.floor(Math.random() * 16777215)] as [ProvisionalId, Color]))
        const uiManager = buildUIManager(
            editChapterData.chapterContent.chapterContentText, 
            entries.flatMap((entry) => entry.labels.map((label) => ({
                id: label.labelId, 
                interval: { start: label.labelStart, end: label.labelEnd}, 
                style: [ 
                    {
                        color: colourMapping.get(entry.labelGroup.labelGroupId)!
                    },  
                    { 
                        visible: true, 
                        mutable: entry.role === "editor" || entry.role === "owner", 
                        cursorStatus: "none",
                        active: false
                    }
                ]}
            )))
        )

        requestManager.attachControllerSignalHandler(dataManager.handleSignal)
        return {
            idRepo,
            requestManager,
            provisionalChapterContentId,
            entries,
            dataManager,
            colourMapping,
            uiManager
        }
    }