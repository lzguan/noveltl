import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, expect, it, vi } from "vitest";
import {
	addConventionMemoryGroupsMemoryGroupIdConventionsPost,
	readConventionsMemoryGroupsMemoryGroupIdConventionsGet,
} from "@/api/endpoints/default/default";
import type { ConventionRead } from "@/api/models";
import { ConventionsBrowser } from "./ConventionsBrowser";

// Replace HTTP only; keep the browser, dialog, and pagination real.
vi.mock("@/api/endpoints/default/default", async (importOriginal) => ({
	...(await importOriginal<typeof import("@/api/endpoints/default/default")>()),
	readConventionsMemoryGroupsMemoryGroupIdConventionsGet: vi.fn(),
	addConventionMemoryGroupsMemoryGroupIdConventionsPost: vi.fn(),
}));

const convention: ConventionRead = {
	conventionId: "convention-1",
	memoryGroupId: "group-1",
	category: "naming",
	title: "Floral codenames",
	rule: "Use the established rendering, e.g. 樱 → Sakura.",
	rationale: null,
	reviewStatus: "pending",
	creatorType: "user",
	createdAt: "2026-11-03T00:00:00Z",
	updatedAt: "2026-11-03T00:00:00Z",
};
function ok<T>(data: T) {
	return { data, status: 200 as const, headers: new Headers() };
}
function created<T>(data: T) {
	return { data, status: 201 as const, headers: new Headers() };
}

beforeAll(() => {
	class Observer implements ResizeObserver {
		disconnect() {}
		observe() {}
		unobserve() {}
	}
	vi.stubGlobal("ResizeObserver", Observer);
});
beforeEach(() => {
	vi.resetAllMocks();
	vi.mocked(readConventionsMemoryGroupsMemoryGroupIdConventionsGet).mockResolvedValue(
		ok({ count: 0, rows: [] }),
	);
});

it("creates a convention with trimmed fields and shows it after reloading", async () => {
	vi.mocked(addConventionMemoryGroupsMemoryGroupIdConventionsPost).mockResolvedValue(
		created(convention),
	);
	render(<ConventionsBrowser memoryGroupId="group-1" />);
	expect(await screen.findByText("No conventions")).toBeInTheDocument();

	vi.mocked(readConventionsMemoryGroupsMemoryGroupIdConventionsGet).mockResolvedValue(
		ok({ count: 1, rows: [convention] }),
	);
	fireEvent.click(screen.getByRole("button", { name: "New convention" }));
	fireEvent.change(screen.getByLabelText("Title"), { target: { value: "  Floral codenames " } });
	fireEvent.change(screen.getByLabelText("Rule"), { target: { value: " 樱 → Sakura " } });
	fireEvent.change(screen.getByLabelText("Rationale"), { target: { value: "   " } });
	fireEvent.click(screen.getByRole("button", { name: "Save convention" }));

	await waitFor(() =>
		expect(addConventionMemoryGroupsMemoryGroupIdConventionsPost).toHaveBeenCalledWith(
			"group-1",
			{ category: "naming", title: "Floral codenames", rule: "樱 → Sakura", rationale: null },
		),
	);
	expect(await screen.findByText("Floral codenames")).toBeInTheDocument();
	expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("does not submit a convention without a rule", async () => {
	render(<ConventionsBrowser memoryGroupId="group-1" />);
	fireEvent.click(await screen.findByRole("button", { name: "New convention" }));
	fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Register" } });
	fireEvent.click(screen.getByRole("button", { name: "Save convention" }));

	expect(await screen.findByText("Rule is required.")).toBeInTheDocument();
	expect(addConventionMemoryGroupsMemoryGroupIdConventionsPost).not.toHaveBeenCalled();
});
