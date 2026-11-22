import { Effect } from "effect";
import type {
	ChapterGetters,
	NovelGetters,
	NovelUserEvent,
} from "../controller/types/controllerTypes";
import { NotFoundException } from "../controller/types/errors";
import type { ChapterGetterSlot, LabelDataSlot } from "../controller/types/helperTypes";
import { Prov } from "../controller/types/helperTypes";
import { CCProvId, CProvId, LDProvId, LGProvId } from "../controller/types/idTypes";
import { reloadLabelGroupInLoadedChapters } from "./reloadLabelGroup";

const GROUP_ID = LGProvId("group");
const unusedGetter = () => Effect.die("unused getter");

function labelDataSlot(): LabelDataSlot {
	return {
		inFlight: 0,
		status: "idle",
		meta: {
			labelData: Prov({
				labelDataId: LDProvId("label-data"),
				chapterContentId: CCProvId("content"),
				labelGroupId: GROUP_ID,
			}),
		},
	};
}

function chapterSlot(
	chapterId: CProvId,
	{ hasGroup, destroyed = false }: { hasGroup: boolean; destroyed?: boolean },
): ChapterGetterSlot {
	const chapterGetters: ChapterGetters = {
		text: unusedGetter,
		chapterContentId: unusedGetter,
		labelDataSlot: () =>
			hasGroup ? Effect.succeed(labelDataSlot()) : Effect.fail(new NotFoundException()),
		isDestroyed: () => destroyed,
		isTextSynced: () => true,
	};
	return {
		inFlight: 0,
		status: "ready",
		meta: {
			chapter: Prov({
				chapterNum: 1,
				chapterTitle: "title",
				chapterIsPublic: false,
				novelId: "novel",
				chapterId,
			}),
		},
		data: { chapterGetters },
	};
}

function gettersFor(slots: Map<CProvId, ChapterGetterSlot | "loading">): NovelGetters {
	return {
		novel: unusedGetter,
		role: unusedGetter,
		labelGroupIds: unusedGetter,
		chapterIds: () => Effect.succeed([...slots.keys()]),
		chapterIdFromServerId: unusedGetter,
		chapterServerId: unusedGetter,
		chapterContentServerId: unusedGetter,
		chapterContentIdFromServerId: unusedGetter,
		labelIdFromServerId: unusedGetter,
		labelGroupIdFromServerId: unusedGetter,
		labelGroupServerId: unusedGetter,
		chapterGetterSlot: (chapterId) => {
			const slot = slots.get(chapterId);
			if (slot === undefined) return Effect.fail(new NotFoundException());
			if (slot === "loading") {
				return Effect.succeed({
					inFlight: 1,
					status: "loading",
					meta: chapterSlot(chapterId, { hasGroup: true }).meta,
				});
			}
			return Effect.succeed(slot);
		},
		labelGroupSlot: unusedGetter,
		autoLabelRunIds: unusedGetter,
		autoLabelRunSlot: unusedGetter,
	};
}

test("reloads the group in loaded chapters that have it, the active chapter first", () => {
	const [loaded, withoutGroup, loading, destroyed, active] = [
		"loaded",
		"without-group",
		"loading",
		"destroyed",
		"active",
	].map(CProvId);
	const getters = gettersFor(
		new Map<CProvId, ChapterGetterSlot | "loading">([
			[loaded, chapterSlot(loaded, { hasGroup: true })],
			[withoutGroup, chapterSlot(withoutGroup, { hasGroup: false })],
			[loading, "loading"],
			[destroyed, chapterSlot(destroyed, { hasGroup: true, destroyed: true })],
			[active, chapterSlot(active, { hasGroup: true })],
		]),
	);
	const events: NovelUserEvent[] = [];

	Effect.runSync(
		reloadLabelGroupInLoadedChapters({
			getters,
			controllerUserEvent: (event) => events.push(event),
			labelGroupId: GROUP_ID,
			activeChapterId: active,
		}),
	);

	expect(events).toEqual([
		{ eventType: "loadLabelData", labelGroupId: GROUP_ID, chapterId: active },
		{ eventType: "loadLabelData", labelGroupId: GROUP_ID, chapterId: loaded },
	]);
});
