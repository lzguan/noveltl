import { expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { RightPanel, type RightPanelTab } from "./RightPanel";

function StatefulContent() {
	const [count, setCount] = useState(0);
	return <button onClick={() => setCount((current) => current + 1)}>Count {count}</button>;
}

describe("RightPanel", () => {
	const tabs: readonly [RightPanelTab, RightPanelTab] = [
		{
			value: "first",
			label: "First tab",
			content: <div>First content</div>,
		},
		{
			value: "second",
			label: "Second tab",
			content: <div>Second content</div>,
		},
	];

	it("renders every tab and selects the first by default", () => {
		render(<RightPanel tabs={tabs} />);

		expect(screen.getByRole("separator").parentElement).toHaveClass("h-full", "min-h-0");
		expect(screen.getByRole("tab", { name: "First tab" })).toHaveAttribute(
			"aria-selected",
			"true",
		);
		expect(screen.getByRole("tab", { name: "Second tab" })).toBeInTheDocument();
		expect(screen.getByText("First content")).toBeVisible();
		expect(screen.queryByText("Second content")).not.toBeInTheDocument();
	});

	it("shows the content for the selected tab", () => {
		render(<RightPanel tabs={tabs} />);

		fireEvent.mouseDown(screen.getByRole("tab", { name: "Second tab" }), {
			button: 0,
			ctrlKey: false,
		});

		expect(screen.getByRole("tab", { name: "Second tab" })).toHaveAttribute(
			"aria-selected",
			"true",
		);
		expect(screen.getByText("Second content")).toBeVisible();
		expect(screen.queryByText("First content")).not.toBeInTheDocument();
	});

	it("honors an explicit default tab", () => {
		render(<RightPanel tabs={tabs} defaultValue="second" />);

		expect(screen.getByRole("tab", { name: "Second tab" })).toHaveAttribute(
			"aria-selected",
			"true",
		);
		expect(screen.getByText("Second content")).toBeVisible();
	});

	it("preserves state for content configured to stay mounted", () => {
		render(
			<RightPanel
				tabs={[
					{
						value: "persistent",
						label: "Persistent tab",
						content: <StatefulContent />,
						keepMounted: true,
					},
					{ value: "other", label: "Other tab", content: <div>Other content</div> },
				]}
			/>,
		);

		fireEvent.click(screen.getByRole("button", { name: "Count 0" }));
		fireEvent.mouseDown(screen.getByRole("tab", { name: "Other tab" }), {
			button: 0,
			ctrlKey: false,
		});
		expect(screen.getByText("Other content")).toBeVisible();
		expect(screen.getByText("Count 1")).not.toBeVisible();
		fireEvent.mouseDown(screen.getByRole("tab", { name: "Persistent tab" }), {
			button: 0,
			ctrlKey: false,
		});

		expect(screen.getByRole("button", { name: "Count 1" })).toBeVisible();
	});

	it("defaults to a wider panel and resizes with the keyboard", () => {
		render(<RightPanel tabs={tabs} />);
		const separator = screen.getByRole("separator", { name: "Resize right sidebar" });

		expect(separator.parentElement).toHaveStyle({ width: "448px" });
		fireEvent.keyDown(separator, { key: "ArrowLeft" });
		expect(separator).toHaveAttribute("aria-valuenow", "464");
		fireEvent.keyDown(separator, { key: "ArrowRight" });
		expect(separator).toHaveAttribute("aria-valuenow", "448");
		fireEvent.keyDown(separator, { key: "Home" });
		expect(separator).toHaveAttribute("aria-valuenow", "320");
		fireEvent.keyDown(separator, { key: "End" });
		expect(separator).toHaveAttribute("aria-valuenow", "640");
	});

	it("resizes by dragging the divider", () => {
		Object.defineProperties(HTMLElement.prototype, {
			setPointerCapture: { configurable: true, value: vi.fn() },
			releasePointerCapture: { configurable: true, value: vi.fn() },
		});
		render(<RightPanel tabs={tabs} />);
		const separator = screen.getByRole("separator");

		fireEvent.pointerDown(separator, { pointerId: 1, clientX: 700 });
		fireEvent.pointerMove(separator, { pointerId: 1, clientX: 650 });
		expect(separator).toHaveAttribute("aria-valuenow", "498");
		fireEvent.pointerUp(separator, { pointerId: 1, clientX: 650 });
	});
});
