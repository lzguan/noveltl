import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useWorkflowViewer } from "../../../filters/hooks/useWorkflowViewer";
import { WorkflowDisplayPanel } from "../../../filters/panels/WorkflowDisplayPanel";

export function FiltersPanel({ novelId }: { novelId: string }) {
	const viewer = useWorkflowViewer(novelId);

	return (
		<Tabs defaultValue="viewer" className="h-full min-h-0">
			<TabsList variant="line" className="w-full px-1 pt-1">
				<TabsTrigger value="viewer">Viewer</TabsTrigger>
			</TabsList>
			<TabsContent value="viewer" className="min-h-0 overflow-y-auto p-2">
				<WorkflowDisplayPanel {...viewer} />
			</TabsContent>
		</Tabs>
	);
}
