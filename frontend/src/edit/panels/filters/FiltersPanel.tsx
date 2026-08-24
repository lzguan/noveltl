import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useState } from "react";
import { useWorkflowViewer } from "../../../filters/hooks/useWorkflowViewer";
import { FunctionDefinitionPanel } from "../../../filters/panels/FunctionDefinitionPanel";
import { RunnerPanel } from "../../../filters/panels/RunnerPanel";
import { WorkflowDisplayPanel } from "../../../filters/panels/WorkflowDisplayPanel";
import type { CCServId, CServId } from "@/edit/controller/types/idTypes";

export function FiltersPanel({
	novelId,
	gotoText,
}: {
	novelId: string;
	gotoText?: (
		chapterId: CServId,
		reference: { start: number; end: number; ccServId: CCServId },
	) => void;
}) {
	const [activeSubpanel, setActiveSubpanel] = useState("viewer");
	const viewer = useWorkflowViewer(novelId);

	return (
		<Tabs value={activeSubpanel} onValueChange={setActiveSubpanel} className="h-full min-h-0">
			<TabsList variant="line" className="w-full px-1 pt-1">
				<TabsTrigger value="viewer">Viewer</TabsTrigger>
				<TabsTrigger value="functions">Functions</TabsTrigger>
				<TabsTrigger value="runners">Runners</TabsTrigger>
			</TabsList>
			<TabsContent value="viewer" className="min-h-0 overflow-y-auto p-2">
				<WorkflowDisplayPanel {...viewer} gotoText={gotoText} />
			</TabsContent>
			<TabsContent value="functions" className="min-h-0 overflow-y-auto p-2">
				<FunctionDefinitionPanel />
			</TabsContent>
			<TabsContent value="runners" className="min-h-0 overflow-y-auto p-2">
				<RunnerPanel novelId={novelId} enabled={activeSubpanel === "runners"} />
			</TabsContent>
		</Tabs>
	);
}
