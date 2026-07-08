import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function RightPanel({ children }: { children?: React.ReactNode }) {
	return (
		<Tabs defaultValue="auto-labels" className="h-full flex flex-col">
			<TabsList variant="line" className="w-full px-1 pt-1">
				<TabsTrigger value="auto-labels">Auto Labels</TabsTrigger>
			</TabsList>
			<TabsContent value="auto-labels" className="min-h-0 flex-1 overflow-hidden p-0">
				{children ?? (
					<div className="text-xs text-muted-foreground">
						Auto-labeling not yet available.
					</div>
				)}
			</TabsContent>
		</Tabs>
	);
}
