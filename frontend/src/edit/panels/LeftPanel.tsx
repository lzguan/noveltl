import type { CProvId, LGProvId, ProvChapter } from "../controller/types/idTypes";
import type { LabelGroupView } from "../hooks/useTrackedLabelGroups";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChapterPanel } from "./chapters/ChapterPanel";
import { LabelGroupPanel } from "./labelGroups/LabelGroupPanel";
import { TermSearchPanel, type GotoText } from "./termSearch/TermSearchPanel";
import { useState } from "react";

export function LeftPanel({
	novelId,
	gotoText,
	chapters,
	currentChapterId,
	onSwitchChapter,
	onAddChapter,
	labelGroups,
	chapterOpen,
	onToggleVisibility,
	activeId,
	onSetActive,
	onAddLabelGroup,
	onReloadLabelData,
}: {
	novelId: string;
	gotoText: GotoText;
	chapters: ProvChapter[];
	currentChapterId: CProvId | null;
	onSwitchChapter: (id: CProvId) => void;
	onAddChapter: (num: number, title: string, isPublic: boolean) => void;
	labelGroups: [LGProvId, LabelGroupView][];
	chapterOpen: boolean;
	onToggleVisibility: (id: LGProvId) => void;
	activeId: LGProvId | null;
	onSetActive: (id: LGProvId | null) => void;
	onAddLabelGroup: (name: string) => void;
	onReloadLabelData: (id: LGProvId) => void;
}) {
	const [tab, setTab] = useState("chapters");
	return (
		<Tabs value={tab} onValueChange={setTab} className="h-full flex flex-col">
			<TabsList
				variant="line"
				className="w-full shrink-0 justify-start overflow-x-auto overflow-y-hidden px-1 pt-1 group-data-horizontal/tabs:h-auto"
			>
				<TabsTrigger value="chapters" className="flex-none">
					Chapters
				</TabsTrigger>
				<TabsTrigger value="label-groups" className="flex-none">
					Labels
				</TabsTrigger>
				<TabsTrigger value="search" className="flex-none">
					Search
				</TabsTrigger>
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
					activeId={activeId}
					onToggleVisibility={onToggleVisibility}
					onSetActive={onSetActive}
					onAddLabelGroup={onAddLabelGroup}
					onReloadLabelData={onReloadLabelData}
				/>
			</TabsContent>
			{/* Kept mounted so results survive switching tabs. */}
			<TabsContent
				value="search"
				forceMount
				hidden={tab !== "search"}
				className="min-h-0 flex-1"
			>
				<TermSearchPanel novelId={novelId} chapters={chapters} gotoText={gotoText} />
			</TabsContent>
		</Tabs>
	);
}
