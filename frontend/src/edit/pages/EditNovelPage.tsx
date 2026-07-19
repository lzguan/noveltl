import { useEffect, useMemo, useState } from "react";
import { Effect } from "effect";
import {
	readAutoLabelRunsAutoLabelRunsGet,
	readChaptersByNovelChaptersGet,
	readLabelGroupsWithRoleLabelGroupsWithRoleGet,
	readNovelWithContributorsNovelsNovelIdWithContributorsGet,
} from "@/api/endpoints/default/default";
import type { Chapter, LabelGroupWithRole, Novel } from "@/api/models";
import { buildNovelController } from "../controller/controller";
import type { NovelData } from "../controller/novelDataManager";
import { Prov } from "../controller/types/helperTypes";
import type { ProvChapter } from "../controller/types/idTypes";
import { generateRandomColor } from "@/edit/lib/text-model/builtin/colors";
import { useEditorState } from "../hooks/useEditorState";
import { useChapters } from "../hooks/useChapters";
import { useTrackedLabelGroups } from "../hooks/useTrackedLabelGroups";
import { useAutoLabelState } from "../hooks/useAutoLabelState";
import { useAutoLabelPreview } from "../hooks/useAutoLabelPreview";
import { useWorkspaceLock } from "../hooks/useWorkspaceLock";
import { createChapterManager } from "../managers/chapterManager";
import { createLabelGroupManager } from "../managers/labelGroupManager";
import { createEditorManager } from "../managers/editorManager";
import { createErrorManager } from "../managers/errorManager";
import { createAutoLabelManager } from "../managers/autolabelManager";
import { makeActiveGroupLabelSource } from "../labeling/activeGroupLabelSource";
import type { LabelEditing, LabelSink } from "../labeling/types";
import { AutoLabelPanel } from "../panels/autoLabels/AutoLabelPanel";
import { EditorPanel } from "../panels/EditorPanel";
import { LeftPanel } from "../panels/LeftPanel";
import { RightPanel } from "../panels/RightPanel";
import { ToolbarPanel } from "../panels/ToolbarPanel";
import type { Role } from "@/api/models/role";
import { LoaderCircle } from "lucide-react";
import { ChapterTabs } from "../panels/chapters/ChapterTabs";

function makeProvChapter(chapter: Chapter, chapterId: ProvChapter["chapterId"]): ProvChapter {
	return Prov({
		chapterNum: chapter.chapterNum,
		chapterTitle: chapter.chapterTitle,
		chapterIsPublic: chapter.chapterIsPublic,
		novelId: chapter.novelId,
		chapterId,
	});
}

export function EditNovelPage() {
	const [novel, setNovel] = useState<{ novel: Novel; role: Role } | null>(null);
	const [novelId, setNovelId] = useState<string | null>(null);
	const [chapters, setChapters] = useState<Chapter[] | null>(null);
	const [labelGroups, setLabelGroups] = useState<LabelGroupWithRole[] | null>(null);
	const [autoLabelRuns, setAutoLabelRuns] = useState<NovelData["autoLabelRuns"] | null>(null);
	const [error, setError] = useState<unknown>(null);

	const editorState = useEditorState();
	const chapterState = useChapters();
	const trackedLabelGroups = useTrackedLabelGroups();
	const autoLabels = useAutoLabelState();
	const autoLabelPreview = useAutoLabelPreview();
	const { workspaceLock, acquireLock, releaseLock } = useWorkspaceLock();

	const [managers, setManagers] = useState<{
		chapterMgr: ReturnType<typeof createChapterManager>;
		labelGroupMgr: ReturnType<typeof createLabelGroupManager>;
		editorMgr: ReturnType<typeof createEditorManager>;
		autoLabelMgr: ReturnType<typeof createAutoLabelManager>;
	} | null>(null);

	const labeling = useMemo<LabelEditing>(() => {
		const source = makeActiveGroupLabelSource({
			getSegmentManager: () => {
				const data = editorState.dataRef.current;
				return data.empty || data.loading ? null : data.segmentManager;
			},
			getActiveGroupId: () => trackedLabelGroups.activeLabelGroupIdRef.current,
			getGroups: () => trackedLabelGroups.labelGroupsRef.current,
		});
		const sink: LabelSink = {
			add: (target, range, meta) => {
				managers?.editorMgr.labelOp(
					{
						op: "add",
						startPos: range.start,
						endPos: range.end,
						word: range.word,
						entityGroup: meta.entityGroup,
						score: meta.score,
						dirty: meta.dirty,
					},
					target,
				);
			},
			remove: (target, range) => {
				managers?.editorMgr.labelOp(
					{ op: "delete", startPos: range.start, endPos: range.end, word: range.word },
					target,
				);
			},
		};
		return { source, sink };
	}, [
		managers,
		editorState.dataRef,
		trackedLabelGroups.labelGroupsRef,
		trackedLabelGroups.activeLabelGroupIdRef,
	]);

	// Fetch data
	useEffect(() => {
		if (!novelId) return;
		readNovelWithContributorsNovelsNovelIdWithContributorsGet(novelId)
			.then((resp) => {
				if (resp.status !== 200) throw new Error(`Failed to load novel: ${resp.status}`);
				setNovel({ novel: resp.data.novel, role: "owner" }); // temporarily owner, will change to role of user with id equal to current logged in user once user state in global store
				setError(null);
			})
			.then(() => readChaptersByNovelChaptersGet({ novelId }))
			.then((resp) => {
				if (resp.status !== 200) throw new Error(`Failed to load chapters: ${resp.status}`);
				setChapters(resp.data);
			})
			.then(() => readLabelGroupsWithRoleLabelGroupsWithRoleGet({ novelId }))
			.then((resp) => {
				if (resp.status !== 200)
					throw new Error(`Failed to load label groups: ${resp.status}`);
				setLabelGroups(resp.data);
			})
			.then(() => readAutoLabelRunsAutoLabelRunsGet({ novelId }))
			.then((resp) => {
				if (resp.status !== 200)
					throw new Error(`Failed to load auto label runs: ${resp.status}`);
				setAutoLabelRuns(resp.data);
			})
			.catch(setError);
	}, [novelId]);

	// Build controller + managers + seed hooks
	useEffect(() => {
		if (novel === null || chapters === null || labelGroups === null || autoLabelRuns === null)
			return;

		const novelData: NovelData = {
			novel: novel.novel,
			novelRole: novel.role,
			labelGroups: labelGroups,
			chapters: chapters,
			autoLabelRuns: autoLabelRuns,
		};
		const ctrl = Effect.runSync(buildNovelController(novelData));

		const controllerUserEvent = (event: Parameters<typeof ctrl.handleUserEvent>[0]) => {
			setTimeout(() => {
				Effect.runPromise(ctrl.handleUserEvent(event)).catch(() => {});
			}, 0);
		};

		const chapterMgr = createChapterManager({
			controllerUserEvent,
			chapters: chapterState,
			setLoading: editorState.setLoading,
			labelGroupsRef: trackedLabelGroups.labelGroupsRef,
		});
		const labelGroupMgr = createLabelGroupManager({
			controllerUserEvent,
			controllerGetters: ctrl.getters,
			trackedLabelGroups,
			dataRef: editorState.dataRef,
		});
		const editorMgr = createEditorManager({
			controllerUserEvent,
			dataRef: editorState.dataRef,
			modeRef: editorState.modeRef,
			setLoading: editorState.setLoading,
			labelGroupsRef: trackedLabelGroups.labelGroupsRef,
			activeChapterIdRef: chapterState.activeChapterIdRef,
			activeGroupIdRef: trackedLabelGroups.activeLabelGroupIdRef,
		});
		const autoLabelMgr = createAutoLabelManager({
			controllerUserEvent,
			controllerGetters: ctrl.getters,
			autoLabels,
			autoLabelPreview,
			dataRef: editorState.dataRef,
			modeRef: editorState.modeRef,
			setMode: editorState.setMode,
			acquireLock,
			releaseLock,
		});
		const errorMgr = createErrorManager();

		ctrl.subscribe(chapterMgr.handleControllerEvent);
		ctrl.subscribe(labelGroupMgr.handleControllerEvent);
		ctrl.subscribe(editorMgr.handleControllerEvent, 0);
		ctrl.subscribe(autoLabelMgr.handleControllerEvent);
		ctrl.subscribe(errorMgr.handleTriggerEvent);

		Effect.runSync(
			autoLabelMgr.handleControllerEvent(ctrl.getters, {
				eventType: "autoLabelRunsRefreshed",
			}),
		);

		// Seed chapters from controller
		Effect.runSync(
			Effect.gen(function* () {
				const ids = yield* ctrl.getters.chapterIds();
				for (let i = 0; i < ids.length; i++) {
					chapterState.addChapter(makeProvChapter(chapters[i], ids[i]));
				}
			}),
		);

		// Seed label groups from controller
		Effect.runSync(
			Effect.gen(function* () {
				const ids = yield* ctrl.getters.labelGroupIds();
				for (const id of ids) {
					const slot = yield* ctrl.getters
						.labelGroupSlot(id)
						.pipe(Effect.catchAll(() => Effect.succeed(null)));
					if (!slot) continue;
					trackedLabelGroups.setLabelGroup(id, {
						labelGroup: Prov({
							labelGroupName: slot.meta?.labelGroup?.labelGroupName ?? "???",
						}),
						color: generateRandomColor(),
						visible: true,
						status: "idle",
					});
				}
			}),
		);

		Effect.runFork(ctrl.start());

		setManagers({ chapterMgr, labelGroupMgr, editorMgr, autoLabelMgr });
		// oxlint-disable-next-line react-hooks/exhaustive-deps
	}, [novel, chapters, labelGroups, autoLabelRuns]);

	// Extract novelId from URL
	useEffect(() => {
		const pathParts = window.location.pathname.split("/");
		const nidIdx = pathParts.indexOf("novels");
		if (nidIdx >= 0 && pathParts[nidIdx + 1]) {
			setNovelId(pathParts[nidIdx + 1]);
		}
	}, []);

	if (error) {
		return (
			<div className="flex items-center justify-center h-full text-sm text-destructive">
				{String(error)}
			</div>
		);
	}

	if (!managers) {
		return (
			<div className="flex items-center justify-center h-full text-sm text-muted-foreground">
				Loading...
			</div>
		);
	}

	const currentChapterId = chapterState.activeChapterId;

	return (
		<div className="relative h-full min-h-0">
			<div className="flex h-full min-h-0 flex-col" inert={workspaceLock !== null}>
				<ToolbarPanel
					mode={editorState.mode}
					loading={!editorState.data.empty && editorState.data.loading}
					onSetMode={editorState.setMode}
				/>
				<div className="flex flex-1 min-h-0 overflow-hidden">
					<div className="w-56 border-r shrink-0 flex flex-col min-h-0">
						<LeftPanel
							chapters={chapterState.chapterList}
							currentChapterId={currentChapterId}
							onSwitchChapter={managers.chapterMgr.switchChapter}
							onAddChapter={managers.chapterMgr.addChapter}
							labelGroups={trackedLabelGroups.labelGroups}
							chapterOpen={!editorState.data.empty && !editorState.data.loading}
							onToggleVisibility={managers.labelGroupMgr.toggleVisibility}
							onSetActive={managers.labelGroupMgr.setActive}
							onAddLabelGroup={managers.labelGroupMgr.addLabelGroup}
							onReloadLabelData={managers.labelGroupMgr.reloadLabelData}
							activeId={trackedLabelGroups.activeLabelGroupId}
						/>
					</div>
					<div className="flex min-w-0 flex-1 flex-col overflow-hidden">
						<ChapterTabs
							tabs={chapterState.tabs}
							chapters={chapterState.chapterList}
							activeChapterId={chapterState.activeChapterId}
							onActivate={managers.chapterMgr.switchChapter}
							onClose={managers.chapterMgr.closeChapter}
						/>
						<EditorPanel
							data={editorState.data}
							mode={editorState.mode}
							onSetCaret={editorState.setCaret}
							onTextOp={managers.editorMgr.textOp}
							labeling={labeling}
							preview={autoLabelPreview.preview}
						/>
					</div>
					<div className="w-80 border-l shrink-0 flex flex-col min-h-0">
						<RightPanel
							tabs={[
								{
									value: "auto-labels",
									label: "Auto Labels",
									content: (
										<AutoLabelPanel
											autoLabels={autoLabels}
											autoLabelManager={managers.autoLabelMgr}
											chapters={chapterState.chapterList}
											currentChapterId={currentChapterId}
											labelGroups={trackedLabelGroups.labelGroups}
											setActive={managers.labelGroupMgr.setActive}
											previewEnabled={autoLabelPreview.enabled}
											previewLoading={autoLabelPreview.loading}
											onSetPreviewEnabled={
												managers.autoLabelMgr.setPreviewEnabled
											}
											activeId={trackedLabelGroups.activeLabelGroupId}
										/>
									),
								},
							]}
						/>
					</div>
				</div>
			</div>
			{workspaceLock !== null && (
				<div className="absolute inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-[1px]">
					<div
						role="status"
						aria-live="polite"
						className="flex items-center gap-2 rounded-md border bg-background px-4 py-3 text-sm shadow-lg"
					>
						<LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
						<span>{workspaceLock.message}</span>
					</div>
				</div>
			)}
		</div>
	);
}
