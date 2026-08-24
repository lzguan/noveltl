import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import {
	readAllLanguagesLanguagesGet,
	readNovelsMineNovelsMineGet,
} from "@/api/endpoints/default/default";
import { NovelType, Visibility, type Novel } from "@/api/models";
import { EditDashboardPage } from "./EditDashboardPage";

vi.mock("@/api/endpoints/default/default", async (importOriginal) => {
	const original = await importOriginal<typeof import("@/api/endpoints/default/default")>();
	return {
		...original,
		readAllLanguagesLanguagesGet: vi.fn(),
		readNovelsMineNovelsMineGet: vi.fn(),
	};
});

const novel: Novel = {
	languageCode: "ja",
	novelId: "00000000-0000-4000-8000-000000000001",
	novelTitle: "Test Novel",
	novelType: NovelType.original,
	novelVisibility: Visibility.NUMBER_0,
	sourceWorkId: "00000000-0000-4000-8000-000000000002",
};

function renderDashboard() {
	return render(
		<MemoryRouter>
			<EditDashboardPage />
		</MemoryRouter>,
	);
}

describe("EditDashboardPage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(readAllLanguagesLanguagesGet).mockResolvedValue({
			data: [
				{ languageCode: "en", languageName: "English" },
				{ languageCode: "ja", languageName: "Japanese" },
			],
			headers: new Headers(),
			status: 200,
		});
	});

	it("opens the upload dialog with the editable novels", async () => {
		vi.mocked(readNovelsMineNovelsMineGet).mockResolvedValue({
			data: [novel],
			headers: new Headers(),
			status: 200,
		});
		renderDashboard();

		const uploadButton = screen.getByRole("button", { name: "Upload chapters" });
		await waitFor(() => expect(uploadButton).toBeEnabled());
		fireEvent.click(uploadButton);

		expect(await screen.findByRole("dialog", { name: "Upload chapters" })).toBeVisible();
		expect(screen.getByRole("combobox", { name: "Novel" })).toBeVisible();
	});

	it("disables chapter uploads when there are no editable novels", async () => {
		vi.mocked(readNovelsMineNovelsMineGet).mockResolvedValue({
			data: [],
			headers: new Headers(),
			status: 200,
		});
		renderDashboard();

		await screen.findByText("No novels found");
		expect(screen.getByRole("button", { name: "Upload chapters" })).toBeDisabled();
	});
});
