import { Profiler, useEffect, useMemo, useState } from "react";
import { Effect } from "effect";
import { readChaptersByNovelChaptersGet, readLabelGroupsWithRoleLabelGroupsWithRoleGet, readNovelNovelsNovelIdGet } from "@/api/endpoints/default/default";
import type { Chapter, LabelGroupWithRole, Novel } from "@/api/models";
import { buildNovelController } from "../controller/controller";
import type { NovelData } from "../controller/dataManager";
import { Prov } from "../controller/types/helperTypes";
import type { ProvChapter } from "../controller/types/idTypes";
import { generateRandomColor } from "@/components/labeled-text-lib/builtin/colors";
import { useEditorState } from "../hooks/useEditorState";
import { useChapterList } from "../hooks/useChapterList";
import { useTrackedLabelGroups } from "../hooks/useTrackedLabelGroups";
import { createChapterManager } from "../managers/chapterManager";
import { createLabelGroupManager } from "../managers/labelGroupManager";
import { createEditorManager } from "../managers/editorManager";
import { buildErrorManager } from "../managers/errorManager";
import { makeActiveGroupLabelSource } from "../labeling/activeGroupLabelSource";
import type { LabelEditing, LabelSink } from "../labeling/types";
import { ChapterPanel } from "../panels/ChapterPanel";
import { EditorPanel } from "../panels/EditorPanel";
import { LabelGroupPanel } from "../panels/LabelGroupPanel";
import { ToolbarPanel } from "../panels/ToolbarPanel";

function makeNovelData(novel: Novel, chapters: Chapter[], labelGroups: LabelGroupWithRole[]): NovelData {
	return { novel, chapters, labelGroups, novelRole: "owner" };
}

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
	const [novel, setNovel] = useState<Novel | null>(null);
	const [novelId, setNovelId] = useState<string | null>(null);
	const [chapters, setChapters] = useState<Chapter[]>([]);
	const [labelGroups, setLabelGroups] = useState<LabelGroupWithRole[] | null>(null);
	const [error, setError] = useState<unknown>(null);

	const editorState = useEditorState();
	const chapterList = useChapterList();
	const trackedLabelGroups = useTrackedLabelGroups();

	const [managers, setManagers] = useState<{
		chapterMgr: ReturnType<typeof createChapterManager>;
		labelGroupMgr: ReturnType<typeof createLabelGroupManager>;
		editorMgr: ReturnType<typeof createEditorManager>;
	} | null>(null);

	const labeling = useMemo<LabelEditing>(() => {
		const source = makeActiveGroupLabelSource({
			getSegmentManager: () => {
				const data = editorState.dataRef.current;
				return data.loading ? null : data.segmentManager;
			},
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
	}, [managers, editorState.dataRef, trackedLabelGroups.labelGroupsRef]);

	// Fetch data
	useEffect(() => {
		if (!novelId) return;
		readNovelNovelsNovelIdGet(novelId)
			.then((resp) => {
				if (resp.status !== 200) throw new Error(`Failed to load novel: ${resp.status}`);
				setNovel(resp.data);
				setError(null);
			})
			.then(() => readChaptersByNovelChaptersGet({ novelId }))
			.then((resp) => {
				if (resp.status !== 200) throw new Error(`Failed to load chapters: ${resp.status}`);
				setChapters(resp.data);
			})
			.then(() => readLabelGroupsWithRoleLabelGroupsWithRoleGet({ novelId }))
			.then((resp) => {
				if (resp.status !== 200) throw new Error(`Failed to load label groups: ${resp.status}`);
				setLabelGroups(resp.data);
			})
			.catch(setError);
	}, [novelId]);

	// Build controller + managers + seed hooks
	useEffect(() => {
		if (!novel || chapters.length === 0 || !labelGroups) return;

		const novelData = makeNovelData(novel, chapters, labelGroups);
		const ctrl = Effect.runSync(buildNovelController(novelData));

		const controllerUserEvent = (
			event: Parameters<typeof ctrl.handleUserEvent>[0],
		) => {
			setTimeout(() => {
				Effect.runPromise(ctrl.handleUserEvent(event)).catch(() => {});
			}, 0);
		};

		const chapterMgr = createChapterManager({
			controllerUserEvent,
			chapterList,
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
		});
		const errorMgr = buildErrorManager();

		ctrl.subscribe(chapterMgr.handleControllerEvent);
		ctrl.subscribe(labelGroupMgr.handleControllerEvent);
		ctrl.subscribe(editorMgr.handleControllerEvent, 0);
		ctrl.subscribe(errorMgr.handleTriggerEvent);

		// Seed chapters from controller
		Effect.runSync(
			Effect.gen(function* () {
				const ids = yield* ctrl.getters.chapterIds();
				for (let i = 0; i < ids.length; i++) {
					chapterList.addChapter(makeProvChapter(chapters[i], ids[i]));
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
							labelGroupName:
								slot.meta?.labelGroup?.labelGroupName ?? "???",
						}),
						color: generateRandomColor(),
						visible: true,
						active: false,
						status: "idle",
					});
				}
			}),
		);

		Effect.runFork(ctrl.start());

		setManagers({ chapterMgr, labelGroupMgr, editorMgr });
	// oxlint-disable-next-line react-hooks/exhaustive-deps
	}, [novel, chapters, labelGroups]);

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

	const currentChapterId = editorState.data.loading
		? null
		: editorState.data.chapterId;

	return (
		<Profiler
			id="EditNovelPage"
			onRender={(_id, phase, duration) =>
				console.log(`${phase}: ${duration}ms`)
			}
		>
			<div className="flex flex-col h-full min-h-0">
				<ToolbarPanel
					mode={editorState.mode}
					loading={editorState.data.loading}
					onSetMode={editorState.setMode}
				/>
				<div className="flex flex-1 min-h-0 overflow-hidden">
					<div className="w-56 border-r shrink-0 flex flex-col min-h-0">
						<div className="border-b shrink-0 max-h-[45%] overflow-y-auto">
							<ChapterPanel
								chapters={chapterList.chapterList}
								currentChapterId={currentChapterId}
								onSwitchChapter={managers.chapterMgr.switchChapter}
								onAddChapter={managers.chapterMgr.addChapter}
							/>
						</div>
						<div className="flex-1 min-h-0 overflow-y-auto">
							<LabelGroupPanel
								labelGroups={trackedLabelGroups.labelGroups}
								chapterOpen={!editorState.data.loading}
								onToggleVisibility={managers.labelGroupMgr.toggleVisibility}
								onSetActive={managers.labelGroupMgr.setActive}
								onAddLabelGroup={managers.labelGroupMgr.addLabelGroup}
								onReloadLabelData={managers.labelGroupMgr.reloadLabelData}
							/>
						</div>
					</div>
					<EditorPanel
						data={editorState.data}
						mode={editorState.mode}
						onSetCaret={editorState.setCaret}
						onTextOp={managers.editorMgr.textOp}
						labeling={labeling}
					/>
				</div>
			</div>
		</Profiler>
	);
}
