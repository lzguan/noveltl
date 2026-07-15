import { fireEvent, render, screen } from "@testing-library/react";
import { RightPanel, type RightPanelTab } from "./RightPanel";

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
});
