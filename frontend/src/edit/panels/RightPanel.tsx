import { useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const DEFAULT_RIGHT_PANEL_WIDTH = 448;
const MIN_RIGHT_PANEL_WIDTH = 320;
const MAX_RIGHT_PANEL_WIDTH = 640;
const KEYBOARD_RESIZE_STEP = 16;

function clampRightPanelWidth(width: number) {
	return Math.min(Math.max(width, MIN_RIGHT_PANEL_WIDTH), MAX_RIGHT_PANEL_WIDTH);
}

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
	const dragStart = useRef<{ pointerX: number; panelWidth: number } | null>(null);
	const [panelWidth, setPanelWidth] = useState(DEFAULT_RIGHT_PANEL_WIDTH);

	function resizePanel(width: number) {
		setPanelWidth(clampRightPanelWidth(width));
	}

	function startResize(event: PointerEvent<HTMLDivElement>) {
		dragStart.current = { pointerX: event.clientX, panelWidth };
		event.currentTarget.setPointerCapture?.(event.pointerId);
	}

	function continueResize(event: PointerEvent<HTMLDivElement>) {
		if (!dragStart.current) return;
		resizePanel(dragStart.current.panelWidth + dragStart.current.pointerX - event.clientX);
	}

	function stopResize(event: PointerEvent<HTMLDivElement>) {
		dragStart.current = null;
		if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
			event.currentTarget.releasePointerCapture?.(event.pointerId);
		}
	}

	function resizeWithKeyboard(event: KeyboardEvent<HTMLDivElement>) {
		let nextWidth: number | null = null;
		if (event.key === "ArrowLeft") nextWidth = panelWidth + KEYBOARD_RESIZE_STEP;
		else if (event.key === "ArrowRight") nextWidth = panelWidth - KEYBOARD_RESIZE_STEP;
		else if (event.key === "Home") nextWidth = MIN_RIGHT_PANEL_WIDTH;
		else if (event.key === "End") nextWidth = MAX_RIGHT_PANEL_WIDTH;
		if (nextWidth === null) return;
		event.preventDefault();
		resizePanel(nextWidth);
	}

	return (
		<div
			className="relative flex h-full min-h-0 shrink-0 flex-col border-l"
			style={{ width: panelWidth }}
		>
			<div
				role="separator"
				aria-label="Resize right sidebar"
				aria-orientation="vertical"
				aria-valuemin={MIN_RIGHT_PANEL_WIDTH}
				aria-valuemax={MAX_RIGHT_PANEL_WIDTH}
				aria-valuenow={panelWidth}
				tabIndex={0}
				className="absolute inset-y-0 left-0 z-10 w-2 -translate-x-1 cursor-col-resize touch-none outline-none hover:bg-accent focus-visible:bg-accent"
				onPointerDown={startResize}
				onPointerMove={continueResize}
				onPointerUp={stopResize}
				onPointerCancel={stopResize}
				onKeyDown={resizeWithKeyboard}
			/>
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
		</div>
	);
}
