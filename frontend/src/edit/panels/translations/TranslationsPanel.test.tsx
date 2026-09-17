import { fireEvent, render, screen, within } from "@testing-library/react";
import { TranslationsPanel } from "./TranslationsPanel";

// The prototype lets users build compatible pipelines and try scoped controls
// without submitting work. These interactions must preserve unrelated batches.
describe("Translations prototype", () => {
	it("filters initial actions and removes the dependent suffix when memories are removed", () => {
		render(<TranslationsPanel />);
		fireEvent.click(screen.getByRole("button", { name: "+ Create job" }));
		const dialog = within(screen.getByRole("dialog"));
		expect(dialog.queryByRole("option", { name: "Prune memories" })).not.toBeInTheDocument();
		fireEvent.change(dialog.getByLabelText("Memory group"), {
			target: { value: "Main glossary" },
		});
		fireEvent.change(dialog.getByLabelText("Add stage"), {
			target: { value: "prune_memories" },
		});
		fireEvent.click(dialog.getByRole("button", { name: "Add stage" }));
		expect(dialog.getByRole("option", { name: "Combine chapter" })).toBeInTheDocument();
		expect(dialog.queryByRole("option", { name: "Translate" })).not.toBeInTheDocument();
		fireEvent.change(dialog.getByLabelText("Add stage"), {
			target: { value: "combine_chapter" },
		});
		fireEvent.click(dialog.getByRole("button", { name: "Add stage" }));
		fireEvent.change(dialog.getByLabelText("Memory group"), { target: { value: "" } });
		expect(dialog.getByText(/Remove stages 1–2/)).toBeInTheDocument();
		fireEvent.click(dialog.getByRole("button", { name: "Remove stages" }));
		expect(dialog.getByText("Add your first stage below.")).toBeInTheDocument();
		expect(dialog.getByRole("button", { name: "Create job" })).toBeDisabled();
	});
	it("saves schema configuration and creates an unstarted job", () => {
		render(<TranslationsPanel />);
		fireEvent.click(screen.getByRole("button", { name: "+ Create job" }));
		const dialog = within(screen.getByRole("dialog"));
		fireEvent.change(dialog.getByLabelText("Add stage"), { target: { value: "translate" } });
		fireEvent.click(dialog.getByRole("button", { name: "Add stage" }));
		fireEvent.click(dialog.getByRole("button", { name: "Configure" }));
		expect(dialog.getByRole("button", { name: "Create job" })).toBeDisabled();
		fireEvent.change(dialog.getByLabelText(/Target language/), { target: { value: "French" } });
		fireEvent.submit(
			dialog.getByRole("button", { name: "Save configuration" }).closest("form")!,
		);
		expect(dialog.getByText("qwen-plus · French")).toBeInTheDocument();
		fireEvent.click(dialog.getByRole("button", { name: "Create job" }));
		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
		const card = within(
			screen.getByRole("heading", { name: "New translation job" }).closest("article")!,
		);
		expect(card.getByText("Not started")).toBeInTheDocument();
		expect(card.getByRole("button", { name: "Start" })).toBeEnabled();
	});
	it("cancels only the selected batch and can resume after a dispatch failure", () => {
		render(<TranslationsPanel />);
		fireEvent.click(screen.getByText("Prototype · sample data, no jobs submitted"));
		fireEvent.click(screen.getByLabelText("Fail next dispatch"));
		fireEvent.click(screen.getByRole("button", { name: "Show details for Job #12" }));
		expect(screen.getByRole("dialog", { name: "Job #12 · Batches" })).toBeInTheDocument();
		const batch = within(screen.getByRole("heading", { name: "Batch 2" }).closest("section")!);
		fireEvent.click(batch.getByRole("button", { name: "Cancel" }));
		expect(batch.getByText("Cancelled")).toBeInTheDocument();
		const first = within(screen.getByRole("heading", { name: "Batch 1" }).closest("section")!);
		expect(first.getByText("Complete")).toBeInTheDocument();
		fireEvent.click(batch.getByRole("button", { name: "Retry" }));
		expect(batch.getByText("Interrupted")).toBeInTheDocument();
		expect(within(screen.getByRole("dialog")).getByRole("status")).toHaveTextContent(
			"Could not queue work",
		);
		fireEvent.click(batch.getByRole("button", { name: "Resume" }));
		expect(batch.getByText("Running")).toBeInTheDocument();
		fireEvent.click(screen.getByRole("button", { name: "Close" }));
		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
	});
});
