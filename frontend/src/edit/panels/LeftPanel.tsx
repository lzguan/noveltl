import type { CProvId, LGProvId, ProvChapter } from "../controller/types/idTypes";
import type { LabelGroupView } from "../hooks/useTrackedLabelGroups";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChapterPanel } from "./chapters/ChapterPanel";
import { LabelGroupPanel } from "./labelGroups/LabelGroupPanel";

export function LeftPanel({
	chapters,
	currentChapterId,
	onSwitchChapter,
	onAddChapter,
	labelGroups,
	chapterOpen,
	onToggleVisibility,
	onSetActive,
	onAddLabelGroup,
	onReloadLabelData,
}: {
	chapters: ProvChapter[];
	currentChapterId: CProvId | null;
	onSwitchChapter: (id: CProvId) => void;
	onAddChapter: (num: number, title: string, isPublic: boolean) => void;
	labelGroups: [LGProvId, LabelGroupView][];
	chapterOpen: boolean;
	onToggleVisibility: (id: LGProvId) => void;
	onSetActive: (id: LGProvId | null) => void;
	onAddLabelGroup: (name: string) => void;
	onReloadLabelData: (id: LGProvId) => void;
}) {
	return (
		<Tabs defaultValue="chapters" className="h-full flex flex-col">
			<TabsList variant="line" className="w-full px-1 pt-1">
				<TabsTrigger value="chapters">Chapters</TabsTrigger>
				<TabsTrigger value="label-groups">Label Groups</TabsTrigger>
			</TabsList>
			<TabsContent value="chapters" className="overflow-y-auto">
				<ChapterPanel
					chapters={chapters}
					currentChapterId={currentChapterId}
					onSwitchChapter={onSwitchChapter}
					onAddChapter={onAddChapter}
				/>
			</TabsContent>
			<TabsContent value="label-groups" className="overflow-y-auto">
				<LabelGroupPanel
					labelGroups={labelGroups}
					chapterOpen={chapterOpen}
					onToggleVisibility={onToggleVisibility}
					onSetActive={onSetActive}
					onAddLabelGroup={onAddLabelGroup}
					onReloadLabelData={onReloadLabelData}
				/>
			</TabsContent>
		</Tabs>
	);
}
