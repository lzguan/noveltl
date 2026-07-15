import type { ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export type RightPanelTab = Readonly<{
	value: string;
	label: ReactNode;
	content: ReactNode;
}>;

export function RightPanel({
	tabs,
	defaultValue = tabs[0].value,
}: {
	tabs: readonly [RightPanelTab, ...RightPanelTab[]];
	defaultValue?: string;
}) {
	return (
		<Tabs defaultValue={defaultValue} className="h-full flex flex-col">
			<TabsList variant="line" className="w-full px-1 pt-1">
				{tabs.map((tab) => (
					<TabsTrigger key={tab.value} value={tab.value}>
						{tab.label}
					</TabsTrigger>
				))}
			</TabsList>
			{tabs.map((tab) => (
				<TabsContent
					key={tab.value}
					value={tab.value}
					className="min-h-0 flex-1 overflow-hidden p-0"
				>
					{tab.content}
				</TabsContent>
			))}
		</Tabs>
	);
}
