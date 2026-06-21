import { Profiler, useEffect, useRef, useState } from "react";
import { Effect } from "effect";
import { readChaptersByNovelChaptersGet, readLabelGroupsWithRoleLabelGroupsWithRoleGet, readNovelNovelsNovelIdGet } from "@/api/endpoints/default/default";
import type { Chapter, LabelGroupWithRole, Novel } from "@/api/models";
import { buildNovelController } from "../controller/controller";
import type { NovelData } from "../controller/dataManager";
import { buildEditorManager, type EditorManager, type EditorSMC } from "../managers/editorManager";
import { ChapterPanel } from "../panels/ChapterPanel";
import { EditorPanel } from "../panels/EditorPanel";
import { LabelGroupPanel } from "../panels/LabelGroupPanel";
import { ToolbarPanel } from "../panels/ToolbarPanel";

function makeNovelData(novel: Novel, chapters: Chapter[], labelGroups: LabelGroupWithRole[]): NovelData {
	return {
		novel,
		chapters,
		labelGroups,
		novelRole: "owner",
	};
}

export function EditNovelPage() {
	const [novel, setNovel] = useState<Novel | null>(null);
	const [novelId, setNovelId] = useState<string | null>(null);
	const [chapters, setChapters] = useState<Chapter[]>([]);
	const [labelGroups, setLabelGroups] = useState<LabelGroupWithRole[] | null>(null);
	const [editorManager, setEditorManager] = useState<EditorManager | null>(null);
	const [smc, setSmc] = useState<EditorSMC>({ segmentManager: null, chapterId: null });
	const smcRef = useRef(smc);
	smcRef.current = smc;
	const [error, setError] = useState<unknown>(null);

	// Fetch novel + chapters
	useEffect(() => {
		if (!novelId) return;
		readNovelNovelsNovelIdGet(novelId).then((resp) => {
			if (resp.status !== 200) {
				setError(new Error(`Failed to load novel: ${resp.status}`));
				return;
			}
			setNovel(resp.data);
			setError(null);
		}).then(() => {
			return readChaptersByNovelChaptersGet({ novelId });
		}).then((resp) => {
			if (resp.status !== 200) {
				setError(new Error(`Failed to load chapters: ${resp.status}`));
				return;
			}
			setChapters(resp.data);
		}).then(() => {
			return readLabelGroupsWithRoleLabelGroupsWithRoleGet({ novelId });
		}).then((resp) => {
			if (resp.status !== 200) {
				setError(new Error(`Failed to load label groups: ${resp.status}`));
				return;
			}
			setLabelGroups(resp.data);
		}).catch(setError);
	}, [novelId]);

	// Build controller + editor manager once novel + chapters + label groups are loaded
	useEffect(() => {
		if (!novel || chapters.length === 0 || !labelGroups) return;

		const novelData = makeNovelData(novel, chapters, labelGroups);
		const ctrl = Effect.runSync(buildNovelController(novelData));

		// editorManager writes user events back to the controller
		const controllerUserEvent = (event: Parameters<typeof ctrl.handleUserEvent>[0]) => {
			console.time("ctrl.handleUserEvent");
			setTimeout(() => {
				Effect.runPromise(ctrl.handleUserEvent(event)).catch(() => {});
				console.timeEnd("ctrl.handleUserEvent");
			}, 0);
		};

		const em = buildEditorManager(
			smcRef,
			(newSmc) => {
				smcRef.current = newSmc;
				setSmc(newSmc);
			},
			controllerUserEvent,
			ctrl.getters,
		);

		// Subscribe controller triggers → editor manager
		ctrl.subscribe(em.handleTriggerEvent);

		// Start the controller's request-processing loop
		Effect.runFork(ctrl.start());

		setEditorManager(em);
	}, [novel, chapters, labelGroups]);

	// Extract novelId from URL on mount
	useEffect(() => {
		const params = new URLSearchParams(window.location.search);
		const cid = params.get("chapterId");
		if (cid) {
			// Load novel by chapter lookup... for POC just use a hardcoded novel ID
		}
		// POC: just load whatever novel ID is in the URL path
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

	if (!editorManager) {
		return (
			<div className="flex items-center justify-center h-full text-sm text-muted-foreground">
				Loading...
			</div>
		);
	}

	return (
		<Profiler id="EditNovelPage" onRender={(_id, phase, duration) => console.log(`${phase}: ${duration}ms`)}>
		<div className="flex flex-col h-full">
			<ToolbarPanel editorManager={editorManager} />
			<div className="flex flex-1 overflow-hidden">
				<div className="w-56 border-r overflow-y-auto shrink-0 flex flex-col">
					<div className="border-b">
						<ChapterPanel editorManager={editorManager} />
					</div>
					<div className="flex-1 overflow-y-auto">
						<LabelGroupPanel editorManager={editorManager} />
					</div>
				</div>
				<EditorPanel editorManager={editorManager} />
			</div>
		</div>
		</Profiler>
	);
}
