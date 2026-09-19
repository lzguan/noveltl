import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { StageConfigForm } from "./StageConfigForm";

// Action metadata supplies presentation to the stage form. Property names are
// arbitrary: the form must follow titles, controls and sibling dependencies.
it("renders annotated controls and dependencies independently of property names", () => {
	const onSave = vi.fn();
	render(
		<StageConfigForm
			config={{ notes: "Keep this draft" }}
			onSave={onSave}
			schema={{
				type: "object",
				additionalProperties: false,
				required: ["engine"],
				properties: {
					engine: {
						type: "string",
						title: "Engine choice",
						enum: ["one", "two"],
						...{ "x-ui": { control: "select" } },
					},
					notes: {
						type: "string",
						title: "Custom notes",
						...{ "x-ui": { control: "textarea", showAfter: "engine" } },
					},
				},
			}}
		/>,
	);
	expect(screen.queryByLabelText("Custom notes")).not.toBeInTheDocument();
	fireEvent.change(screen.getByRole("combobox", { name: /Engine choice/ }), {
		target: { value: "0" },
	});
	const notes = screen.getByLabelText("Custom notes");
	expect(notes.tagName).toBe("TEXTAREA");
	expect(notes).toHaveValue("Keep this draft");
	fireEvent.change(notes, { target: { value: "Updated" } });
	fireEvent.click(screen.getByRole("button", { name: "Save configuration" }));
	expect(onSave).toHaveBeenCalledWith({ engine: "one", notes: "Updated" });
});
