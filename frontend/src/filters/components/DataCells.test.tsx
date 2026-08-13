import type { MDataType } from "@/api/models";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { MutableDataCell } from "./DataCells";

function Harness({
	value,
	commit,
}: {
	value: MDataType;
	commit: (value: MDataType) => Promise<void>;
}) {
	const [editingLocked, setEditingLocked] = useState(false);
	return (
		<>
			<MutableDataCell
				value={value}
				editLabel="review value"
				editingLocked={editingLocked}
				setEditingLocked={setEditingLocked}
				commit={commit}
			/>
			<MutableDataCell
				value={{ kind: "value", type: "string", value: "other" }}
				editLabel="other value"
				editingLocked={editingLocked}
				setEditingLocked={setEditingLocked}
				commit={vi.fn()}
			/>
		</>
	);
}

describe("MutableDataCell", () => {
	it("acquires the shared lock and cancels with Escape", () => {
		render(
			<Harness value={{ kind: "value", type: "string", value: "draft" }} commit={vi.fn()} />,
		);

		fireEvent.click(screen.getByRole("button", { name: "Edit review value" }));
		expect(screen.getByRole("button", { name: "Edit other value" })).toBeDisabled();
		expect(screen.getByText("Press Enter to save · Esc to cancel")).toBeVisible();

		fireEvent.keyDown(screen.getByRole("textbox", { name: "review value" }), {
			key: "Escape",
		});
		expect(screen.getByRole("button", { name: "Edit other value" })).toBeEnabled();
	});

	it.each([
		{
			value: { kind: "value", type: "string", value: "old" } as const,
			draft: "new",
			expected: { kind: "value", type: "string", value: "new" },
		},
		{
			value: { kind: "value", type: "int", value: 1 } as const,
			draft: "42",
			expected: { kind: "value", type: "int", value: 42 },
		},
		{
			value: { kind: "value", type: "float", value: 1.5 } as const,
			draft: "2.75",
			expected: { kind: "value", type: "float", value: 2.75 },
		},
	])("commits a typed $value.type value", async ({ value, draft, expected }) => {
		const commit = vi.fn().mockResolvedValue(undefined);
		render(<Harness value={value} commit={commit} />);
		fireEvent.click(screen.getByRole("button", { name: "Edit review value" }));
		const input = screen.getByRole(value.type === "string" ? "textbox" : "spinbutton", {
			name: "review value",
		});
		fireEvent.change(input, { target: { value: draft } });
		fireEvent.submit(input.closest("form")!);

		await waitFor(() => expect(commit).toHaveBeenCalledWith(expected));
		await waitFor(() =>
			expect(screen.getByRole("button", { name: "Edit other value" })).toBeEnabled(),
		);
	});

	it("commits a boolean value", async () => {
		const commit = vi.fn().mockResolvedValue(undefined);
		render(<Harness value={{ kind: "value", type: "bool", value: false }} commit={commit} />);
		fireEvent.click(screen.getByRole("button", { name: "Edit review value" }));
		fireEvent.click(screen.getByRole("checkbox"));
		fireEvent.keyDown(screen.getByRole("checkbox"), { key: "Enter" });

		await waitFor(() =>
			expect(commit).toHaveBeenCalledWith({ kind: "value", type: "bool", value: true }),
		);
	});

	it("keeps the editor and lock after validation or commit errors", async () => {
		const commit = vi.fn().mockRejectedValue(new Error("Update rejected"));
		render(<Harness value={{ kind: "value", type: "int", value: 1 }} commit={commit} />);
		fireEvent.click(screen.getByRole("button", { name: "Edit review value" }));
		const input = screen.getByRole("spinbutton", { name: "review value" });

		fireEvent.change(input, { target: { value: "1.5" } });
		fireEvent.submit(input.closest("form")!);
		expect(screen.getByRole("alert")).toHaveTextContent("Enter a whole number.");
		expect(commit).not.toHaveBeenCalled();

		fireEvent.change(input, { target: { value: "2" } });
		fireEvent.submit(input.closest("form")!);
		await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Update rejected"));
		expect(screen.getByRole("button", { name: "Edit other value" })).toBeDisabled();
	});
});
