import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import {
	TargetRole,
	type PublishingTargetMemberRead,
	type PublishingTargetRead,
	type PublishingTargetTestResult,
} from "@/api/models";
import { SettingsPage } from "./SettingsPage";

function jsonResponse(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { "Content-Type": "application/json" },
	});
}

function requestUrl(input: RequestInfo | URL): string {
	if (typeof input === "string") return input;
	if (input instanceof URL) return input.toString();
	return input.url;
}

const ownerTarget: PublishingTargetRead = {
	targetId: "target-1",
	name: "Main Reader",
	apiBaseUrl: "https://reader.example.com/api",
	publicBaseUrl: "https://reader.example.com",
	keyPrefix: "ntr_live",
	role: TargetRole.owner,
	createdByUserId: "user-1",
	createdAt: "2026-11-01T00:00:00Z",
	updatedAt: "2026-11-01T00:00:00Z",
};

const publisherTarget: PublishingTargetRead = {
	targetId: "target-2",
	name: "Staging Reader",
	apiBaseUrl: "https://staging.example.com/api",
	publicBaseUrl: null,
	keyPrefix: "ntr_stag",
	role: TargetRole.publisher,
	createdByUserId: "user-2",
	createdAt: "2026-11-02T00:00:00Z",
	updatedAt: "2026-11-02T00:00:00Z",
};

function renderSettings() {
	return render(
		<MemoryRouter>
			<SettingsPage />
		</MemoryRouter>,
	);
}

describe("SettingsPage publishing targets", () => {
	let fetchSpy: ReturnType<typeof vi.fn<typeof fetch>>;

	beforeEach(() => {
		fetchSpy = vi.fn<typeof fetch>();
		vi.stubGlobal("fetch", fetchSpy);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it("renders an empty state and adds a verified target via Test & save", async () => {
		fetchSpy.mockImplementation(async (input, init) => {
			const url = requestUrl(input);
			const method = init?.method ?? "GET";
			if (url === "/api/publishing/targets" && method === "GET") {
				return jsonResponse(200, []);
			}
			if (url === "/api/publishing/targets" && method === "POST") {
				return jsonResponse(201, ownerTarget);
			}
			return jsonResponse(404, { detail: "Not found" });
		});

		renderSettings();

		expect(await screen.findByText("No publishing targets configured")).toBeVisible();

		fireEvent.click(screen.getAllByRole("button", { name: "Add target" })[0]);
		const dialog = within(await screen.findByRole("dialog", { name: "Add publishing target" }));

		fireEvent.change(dialog.getByLabelText("Name"), { target: { value: "Main Reader" } });
		fireEvent.change(dialog.getByLabelText("API Base URL"), {
			target: { value: "https://reader.example.com/api" },
		});
		fireEvent.change(dialog.getByLabelText("API Key"), {
			target: { value: "ntr_live_secret_token" },
		});
		fireEvent.click(dialog.getByRole("button", { name: "Test & save" }));

		await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
		expect(await screen.findByText("Main Reader")).toBeVisible();
		expect(screen.getByText("ntr_live…")).toBeVisible();
		expect(
			screen.getByRole("link", { name: /https:\/\/reader\.example\.com/ }),
		).toHaveAttribute("href", "https://reader.example.com");
	});

	it("surfaces backend error details when adding a target fails", async () => {
		fetchSpy.mockImplementation(async (input, init) => {
			const url = requestUrl(input);
			const method = init?.method ?? "GET";
			if (url === "/api/publishing/targets" && method === "GET") {
				return jsonResponse(200, []);
			}
			if (url === "/api/publishing/targets" && method === "POST") {
				return jsonResponse(503, {
					detail: "PUBLISH_KEY_ENCRYPTION_SECRET is not configured on this server.",
				});
			}
			return jsonResponse(404, { detail: "Not found" });
		});

		renderSettings();

		await screen.findByText("No publishing targets configured");
		fireEvent.click(screen.getAllByRole("button", { name: "Add target" })[0]);
		const dialog = within(await screen.findByRole("dialog", { name: "Add publishing target" }));

		fireEvent.change(dialog.getByLabelText("Name"), { target: { value: "Broken Target" } });
		fireEvent.change(dialog.getByLabelText("API Base URL"), {
			target: { value: "https://reader.example.com/api" },
		});
		fireEvent.change(dialog.getByLabelText("API Key"), { target: { value: "bad_key" } });
		fireEvent.click(dialog.getByRole("button", { name: "Test & save" }));

		expect(await dialog.findByRole("alert")).toHaveTextContent(
			"PUBLISH_KEY_ENCRYPTION_SECRET is not configured on this server.",
		);
		expect(screen.getByRole("dialog")).toBeInTheDocument();
	});

	it("shows owner-only controls only for owner targets and displays inline test feedback", async () => {
		const testResult: PublishingTargetTestResult = {
			ok: true,
			name: "Reader Prod Instance",
			publicBaseUrl: "https://reader.example.com",
			protocolVersion: 1,
		};

		fetchSpy.mockImplementation(async (input, init) => {
			const url = requestUrl(input);
			const method = init?.method ?? "GET";
			if (url === "/api/publishing/targets" && method === "GET") {
				return jsonResponse(200, [ownerTarget, publisherTarget]);
			}
			if (
				url === `/api/publishing/targets/${ownerTarget.targetId}/test` &&
				method === "POST"
			) {
				return jsonResponse(200, testResult);
			}
			if (
				url === `/api/publishing/targets/${publisherTarget.targetId}/test` &&
				method === "POST"
			) {
				return jsonResponse(401, { detail: "Reader rejected the publish API key." });
			}
			return jsonResponse(404, { detail: "Not found" });
		});

		renderSettings();

		expect(await screen.findByText("Main Reader")).toBeVisible();
		expect(screen.getByText("Staging Reader")).toBeVisible();

		const articles = screen.getAllByRole("article");
		const ownerCard = within(articles[0]);
		const publisherCard = within(articles[1]);

		expect(ownerCard.getByRole("button", { name: "Edit" })).toBeVisible();
		expect(ownerCard.getByRole("button", { name: "Members" })).toBeVisible();
		expect(ownerCard.getByRole("button", { name: "Delete" })).toBeVisible();

		expect(publisherCard.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
		expect(publisherCard.queryByRole("button", { name: "Members" })).not.toBeInTheDocument();
		expect(publisherCard.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();

		fireEvent.click(ownerCard.getByRole("button", { name: "Test connection" }));
		expect(await ownerCard.findByRole("status")).toHaveTextContent(
			"Connected to Reader Prod Instance (https://reader.example.com)",
		);

		fireEvent.click(publisherCard.getByRole("button", { name: "Test connection" }));
		expect(await publisherCard.findByRole("alert")).toHaveTextContent(
			"Reader rejected the publish API key.",
		);
	});

	it("manages target members and surfaces last-owner removal errors", async () => {
		const initialMembers: PublishingTargetMemberRead[] = [
			{
				userId: "user-1",
				userName: "alice",
				role: TargetRole.owner,
				createdAt: "2026-11-01T00:00:00Z",
			},
		];
		const addedMember: PublishingTargetMemberRead = {
			userId: "user-2",
			userName: "bob",
			role: TargetRole.publisher,
			createdAt: "2026-11-03T00:00:00Z",
		};

		fetchSpy.mockImplementation(async (input, init) => {
			const url = requestUrl(input);
			const method = init?.method ?? "GET";
			if (url === "/api/publishing/targets" && method === "GET") {
				return jsonResponse(200, [ownerTarget]);
			}
			if (
				url === `/api/publishing/targets/${ownerTarget.targetId}/members` &&
				method === "GET"
			) {
				return jsonResponse(200, initialMembers);
			}
			if (
				url === `/api/publishing/targets/${ownerTarget.targetId}/members` &&
				method === "POST"
			) {
				return jsonResponse(200, addedMember);
			}
			if (
				url === `/api/publishing/targets/${ownerTarget.targetId}/members/user-1` &&
				method === "DELETE"
			) {
				return jsonResponse(400, { detail: "Cannot remove the last owner of a target." });
			}
			return jsonResponse(404, { detail: "Not found" });
		});

		renderSettings();

		await screen.findByText("Main Reader");
		fireEvent.click(screen.getByRole("button", { name: "Members" }));

		const dialog = within(await screen.findByRole("dialog"));
		expect(await dialog.findByText("alice")).toBeVisible();

		fireEvent.change(dialog.getByLabelText("Username"), { target: { value: "bob" } });
		fireEvent.click(dialog.getByRole("button", { name: "Save" }));
		expect(await dialog.findByText("bob")).toBeVisible();

		fireEvent.click(dialog.getByRole("button", { name: "Remove alice" }));
		expect(await dialog.findByRole("alert")).toHaveTextContent(
			"Cannot remove the last owner of a target.",
		);
		expect(dialog.getByText("alice")).toBeVisible();
	});
});
