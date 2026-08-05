import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useState } from "react";
import { useFunctionDefinitionForm } from "../../../filters/hooks/useFunctionDefinitionForm";
import { useRunnerPanel } from "../../../filters/hooks/runnerForms/useRunnerPanel";
import { useWorkflowViewer } from "../../../filters/hooks/useWorkflowViewer";
import { FunctionDefinitionPanel } from "../../../filters/panels/FunctionDefinitionPanel";
import { RunnerPanel } from "../../../filters/panels/RunnerPanel";
import { WorkflowDisplayPanel } from "../../../filters/panels/WorkflowDisplayPanel";

export function FiltersPanel({ novelId }: { novelId: string }) {
	const [activeSubpanel, setActiveSubpanel] = useState("viewer");
	const viewer = useWorkflowViewer(novelId);
	const functionDefinitionForm = useFunctionDefinitionForm();
	const runnerPanel = useRunnerPanel(novelId, activeSubpanel === "runners");

	return (
		<Tabs value={activeSubpanel} onValueChange={setActiveSubpanel} className="h-full min-h-0">
			<TabsList variant="line" className="w-full px-1 pt-1">
				<TabsTrigger value="viewer">Viewer</TabsTrigger>
				<TabsTrigger value="functions">Functions</TabsTrigger>
				<TabsTrigger value="runners">Runners</TabsTrigger>
			</TabsList>
			<TabsContent value="viewer" className="min-h-0 overflow-y-auto p-2">
				<WorkflowDisplayPanel {...viewer} />
			</TabsContent>
			<TabsContent value="functions" className="min-h-0 overflow-y-auto p-2">
				<FunctionDefinitionPanel {...functionDefinitionForm} />
			</TabsContent>
			<TabsContent value="runners" className="min-h-0 overflow-y-auto p-2">
				<RunnerPanel {...runnerPanel} />
			</TabsContent>
		</Tabs>
	);
}
