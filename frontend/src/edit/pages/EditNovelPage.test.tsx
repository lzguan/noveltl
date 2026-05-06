import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EditNovelPage } from "./EditNovelPage";

const readNovelMock = vi.fn();
const readChaptersMock = vi.fn();
const readEditChapterDataMock = vi.fn();
const createChapterMock = vi.fn();
const useControllerMock = vi.fn();
const buildRuntimeMock = vi.fn();

vi.mock("@/client", async () => {
    const actual = await vi.importActual<typeof import("@/client")>("@/client");
    return {
        ...actual,
        createChapterNovelsNovelIdChaptersPost: createChapterMock,
        readNovelNovelsNovelIdGet: readNovelMock,
        readChaptersByNovelChaptersGet: readChaptersMock,
        readEditChapterDataEditChapterDataChapterIdGet: readEditChapterDataMock,
    };
});

vi.mock("./controller/controller", () => ({
    useController: (...args: unknown[]) => useControllerMock(...args),
}));

vi.mock("./controller/utils", () => ({
    buildRuntime: (...args: unknown[]) => buildRuntimeMock(...args),
}));

vi.mock("@/components/labeled-text-lib/react/DynamicLabeledText", () => ({
    DynamicLabeledText: () => <div data-testid="dynamic-labeled-text">dynamic surface</div>,
}));

function LocationProbe() {
    const location = useLocation();
    return <div data-testid="location-search">{location.search}</div>;
}

function makeNovel() {
    return {
        novelId: "novel-1",
        novelTitle: "Glass Harbor",
        novelDescription: null,
        novelAuthor: "A. Writer",
        novelVisibility: 0,
        novelType: "original",
        languageCode: "en",
        sourceWorkId: "source-1",
    };
}

function makeChapters() {
    return [
        {
            chapterId: "chapter-1",
            chapterNum: 1,
            chapterTitle: "Arrival",
            chapterIsPublic: false,
            novelId: "novel-1",
        },
        {
            chapterId: "chapter-2",
            chapterNum: 2,
            chapterTitle: "Crosswind",
            chapterIsPublic: false,
            novelId: "novel-1",
        },
    ];
}

function makeEditChapterData(role: "owner" | "viewer" | "editor" = "owner") {
    return {
        chapter: {
            chapterId: "chapter-1",
            chapterNum: 1,
            chapterTitle: "Arrival",
            chapterIsPublic: false,
            novelId: "novel-1",
        },
        chapterContent: {
            chapterContentId: "content-1",
            chapterContentText: "Alice met Bob.",
            chapterContentVersion: 3,
        },
        role,
        labelGroupList: [],
        labelDataList: [],
    };
}

function makeRuntime(text: string) {
    const uiManager = {
        getText: () => text,
        subscribe: () => () => {},
        getLabel: vi.fn(),
        addLabel: vi.fn(),
        updateLabel: vi.fn(),
        removeLabel: vi.fn(),
        insertTextAt: vi.fn(),
        deleteTextAt: vi.fn(),
        batch: (callback: () => void) => callback(),
        getSegments: () => [],
        getSegmentIds: () => [],
        getSegment: vi.fn(),
    };

    return {
        idRepo: {
            getServerId: () => "server-id",
        },
        requestManager: {
            attachControllerSignalHandler: vi.fn(),
            isQueueEmpty: () => true,
            start: vi.fn(async () => undefined),
            handleSignal: vi.fn(),
            onUserEvent: vi.fn(),
            send: vi.fn(async () => undefined),
            enqueueRequest: vi.fn(),
        },
        provisionalChapterContentId: "provisional-content",
        entries: [],
        dataManager: {
            getEntries: () => [],
            handleSignal: vi.fn(),
            addLabelGroup: vi.fn(),
            addLabel: vi.fn(),
            deleteLabel: vi.fn(),
            updateLabel: vi.fn(),
            flushLabelOps: () => [],
            insertTextAt: vi.fn(),
            deleteTextAt: vi.fn(),
            flushTextOps: () => [],
        },
        colourMapping: new Map(),
        uiManager,
    };
}

function renderEditor(initialEntry: string) {
    return render(
        <MemoryRouter initialEntries={[initialEntry]}>
            <Routes>
                <Route path="/edit/novels/:novelId" element={<><EditNovelPage loadLabelsNum={3} /><LocationProbe /></>} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("EditNovelPage", () => {
    beforeEach(() => {
        readNovelMock.mockResolvedValue({ data: makeNovel(), error: undefined });
        readChaptersMock.mockResolvedValue({ data: makeChapters(), error: undefined });
        readEditChapterDataMock.mockResolvedValue({ data: makeEditChapterData(), error: undefined });
        buildRuntimeMock.mockImplementation(() => makeRuntime("Alice met Bob."));
        useControllerMock.mockImplementation((_editChapterData, _getMode, _setMode, runtime) => ({
            handleEvent: vi.fn(),
            handleSignal: vi.fn(),
            uiManager: runtime.uiManager,
        }));
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    it("auto-selects the first chapter when chapter-id is missing", async () => {
        renderEditor("/edit/novels/novel-1");

        await waitFor(() => {
            expect(screen.getByTestId("location-search")).toHaveTextContent("?chapter-id=chapter-1");
        });

        expect(readEditChapterDataMock).toHaveBeenCalledWith({
            path: { chapterId: "chapter-1" },
            query: { novelId: "novel-1", labelGroupsNum: 3 },
        });
    });

    it("shows a recoverable invalid chapter state and can jump back to the first chapter", async () => {
        renderEditor("/edit/novels/novel-1?chapter-id=missing");

        expect(await screen.findByText("Selected chapter not found")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: "Jump To First Chapter" }));

        await waitFor(() => {
            expect(screen.getByTestId("location-search")).toHaveTextContent("?chapter-id=chapter-1");
        });
    });

    it("creates the first chapter from the empty state", async () => {
        readChaptersMock
            .mockResolvedValueOnce({ data: [], error: undefined })
            .mockResolvedValueOnce({
                data: [{
                    chapterId: "chapter-9",
                    chapterNum: 9,
                    chapterTitle: "Dawn Trade",
                    chapterIsPublic: false,
                    novelId: "novel-1",
                }],
                error: undefined,
            });
        createChapterMock.mockResolvedValue({
            data: {
                metadata: {
                    chapterId: "chapter-9",
                    chapterNum: 9,
                    chapterTitle: "Dawn Trade",
                    chapterIsPublic: false,
                    novelId: "novel-1",
                },
                content: {
                    chapterContentId: "content-9",
                    chapterContentText: "",
                    chapterContentVersion: 1,
                },
            },
            error: undefined,
        });
        readEditChapterDataMock.mockResolvedValue({
            data: {
                ...makeEditChapterData(),
                chapter: {
                    chapterId: "chapter-9",
                    chapterNum: 9,
                    chapterTitle: "Dawn Trade",
                    chapterIsPublic: false,
                    novelId: "novel-1",
                },
                chapterContent: {
                    chapterContentId: "content-9",
                    chapterContentText: "",
                    chapterContentVersion: 1,
                },
            },
            error: undefined,
        });

        renderEditor("/edit/novels/novel-1");

        expect(await screen.findByText("No chapters yet")).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText("Number"), { target: { value: "9" } });
        fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Dawn Trade" } });
        fireEvent.click(screen.getByRole("button", { name: "Create Chapter" }));

        await waitFor(() => {
            expect(createChapterMock).toHaveBeenCalledWith({
                path: { novelId: "novel-1" },
                body: {
                    chapterNum: 9,
                    chapterTitle: "Dawn Trade",
                    chapterIsPublic: false,
                },
            });
        });

        await waitFor(() => {
            expect(screen.getByTestId("location-search")).toHaveTextContent("?chapter-id=chapter-9");
        });
    });

    it("renders the workspace and disables text editing for viewers", async () => {
        readEditChapterDataMock.mockResolvedValue({ data: makeEditChapterData("viewer"), error: undefined });

        renderEditor("/edit/novels/novel-1?chapter-id=chapter-1");

        expect(await screen.findByText("Glass Harbor")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Edit Text" })).toBeDisabled();
        expect(screen.getByTestId("dynamic-labeled-text")).toBeInTheDocument();
    });
});
