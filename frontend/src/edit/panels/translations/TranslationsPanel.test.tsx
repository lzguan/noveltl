import { fireEvent, render, screen, within } from "@testing-library/react";
import { TranslationsPanel } from "./TranslationsPanel";

// The prototype lets users build compatible pipelines and try scoped controls
// without submitting work. These interactions must preserve unrelated batches.
describe("Translations prototype", () => {
	it("cancels only the selected batch and can resume after a dispatch failure", () => {
		render(<TranslationsPanel novelId="novel" chapterNumbers={[1, 2]} />);
		fireEvent.click(screen.getByText("Sample viewer · simulated controls"));
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
