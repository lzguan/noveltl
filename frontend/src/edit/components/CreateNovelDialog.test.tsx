import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import {
	createNovelNovelsPost,
	readAllLanguagesLanguagesGet,
	readSourceWorksSourceWorksGet,
} from "@/api/endpoints/default/default";
import { NovelType, Visibility, type Novel } from "@/api/models";
import { CreateNovelDialog } from "./CreateNovelDialog";

vi.mock("@/api/endpoints/default/default", async (importOriginal) => {
	const original = await importOriginal<typeof import("@/api/endpoints/default/default")>();
	return {
		...original,
		createNovelNovelsPost: vi.fn(),
		readAllLanguagesLanguagesGet: vi.fn(),
		readSourceWorksSourceWorksGet: vi.fn(),
	};
});

beforeAll(() => {
	Object.defineProperties(HTMLElement.prototype, {
		hasPointerCapture: { configurable: true, value: () => false },
		releasePointerCapture: { configurable: true, value: () => undefined },
		scrollIntoView: { configurable: true, value: () => undefined },
		setPointerCapture: { configurable: true, value: () => undefined },
	});
});

const createdNovel: Novel = {
	languageCode: "ja",
	novelId: "novel-1",
	novelTitle: "Test Novel",
	novelType: NovelType.original,
	novelVisibility: Visibility.NUMBER_0,
	sourceWorkId: "source-created-by-server",
};

function renderDialog(onCreated = vi.fn()) {
	return render(
		<MemoryRouter>
			<CreateNovelDialog open onOpenChange={vi.fn()} onCreated={onCreated} />
		</MemoryRouter>,
	);
}

async function openSelect(name: string) {
	const trigger = await screen.findByRole("combobox", { name });
	await waitFor(() => expect(trigger).toBeEnabled());
	fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false, pointerType: "mouse" });
}

describe("CreateNovelDialog", () => {
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
		vi.mocked(readSourceWorksSourceWorksGet).mockResolvedValue({
			data: [
				{
					novels: [],
					sourceWork: {
						sourceWorkId: "source-1",
						sourceWorkTitle: "Existing Work",
					},
				},
			],
			headers: new Headers(),
			status: 200,
		});
		vi.mocked(createNovelNovelsPost).mockResolvedValue({
			data: createdNovel,
			headers: new Headers(),
			status: 200,
		});
	});

	it("does not query source works until a non-empty search is submitted", async () => {
		renderDialog();

		expect(await screen.findByRole("dialog", { name: "Create novel" })).toBeVisible();
		expect(readAllLanguagesLanguagesGet).toHaveBeenCalledOnce();
		expect(readSourceWorksSourceWorksGet).not.toHaveBeenCalled();

		fireEvent.change(screen.getByPlaceholderText("Search source works..."), {
			target: { value: "   " },
		});
		fireEvent.click(screen.getByRole("button", { name: "Search" }));
		expect(readSourceWorksSourceWorksGet).not.toHaveBeenCalled();

		fireEvent.change(screen.getByPlaceholderText("Search source works..."), {
			target: { value: "  Existing  " },
		});
		fireEvent.click(screen.getByRole("button", { name: "Search" }));

		await waitFor(() =>
			expect(readSourceWorksSourceWorksGet).toHaveBeenCalledWith({
				retNovels: false,
				titleContains: "Existing",
			}),
		);
	});

	it("blocks creation until the required fields are provided", async () => {
		renderDialog();

		const createButton = await screen.findByRole("button", { name: "Create novel" });
		await waitFor(() => expect(createButton).toBeEnabled());
		fireEvent.click(createButton);

		expect(await screen.findByText("Title is required.")).toBeVisible();
		expect(screen.getByText("Language is required.")).toBeVisible();
		expect(createNovelNovelsPost).not.toHaveBeenCalled();
	});

	it("submits null sourceWorkId by default", async () => {
		const onCreated = vi.fn();
		renderDialog(onCreated);

		fireEvent.change(await screen.findByLabelText("Title"), {
			target: { value: "Test Novel" },
		});
		await openSelect("Language");
		fireEvent.click(await screen.findByRole("option", { name: "Japanese" }));
		fireEvent.click(screen.getByRole("button", { name: "Create novel" }));

		await waitFor(() =>
			expect(createNovelNovelsPost).toHaveBeenCalledWith({
				languageCode: "ja",
				novelAuthor: null,
				novelDescription: null,
				novelTitle: "Test Novel",
				novelType: NovelType.original,
				novelVisibility: Visibility.NUMBER_0,
				sourceWorkId: null,
			}),
		);
		expect(onCreated).toHaveBeenCalledWith(createdNovel);
	});

	it("submits the selected source work id", async () => {
		renderDialog();

		fireEvent.change(await screen.findByLabelText("Title"), {
			target: { value: "Test Novel" },
		});
		await openSelect("Language");
		fireEvent.click(await screen.findByRole("option", { name: "Japanese" }));
		fireEvent.change(screen.getByPlaceholderText("Search source works..."), {
			target: { value: "Existing" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Search" }));
		await openSelect("Source work results");
		fireEvent.click(await screen.findByRole("option", { name: "Existing Work" }));
		fireEvent.click(screen.getByRole("button", { name: "Create novel" }));

		await waitFor(() =>
			expect(createNovelNovelsPost).toHaveBeenCalledWith(
				expect.objectContaining({ sourceWorkId: "source-1" }),
			),
		);
	});

	it("keeps the form open and preserves its values when creation fails", async () => {
		vi.mocked(createNovelNovelsPost).mockRejectedValueOnce(new Error("offline"));
		renderDialog();

		fireEvent.change(await screen.findByLabelText("Title"), {
			target: { value: "Keep this title" },
		});
		await openSelect("Language");
		fireEvent.click(await screen.findByRole("option", { name: "English" }));
		fireEvent.click(screen.getByRole("button", { name: "Create novel" }));

		expect(await screen.findByText("Could not create the novel.")).toBeVisible();
		expect(screen.getByRole("dialog", { name: "Create novel" })).toBeVisible();
		expect(screen.getByLabelText("Title")).toHaveValue("Keep this title");
	});
});
