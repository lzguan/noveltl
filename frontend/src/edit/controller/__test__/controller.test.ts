import { afterEach, describe, expect, it, vi } from "vitest";

import type { Chapter, EditChapterData, Label, Novel } from "@/client";

import { buildController } from "../controller";
import type {
  LabelGroupView,
  ProvisionalId,
  RequestEvent,
  RequestManager,
  Runtime,
  Signal,
} from "../types";
import { buildRuntime } from "../utils";

type Harness = {
  controller: ReturnType<typeof buildController>;
  runtime: Runtime;
  requestManager: RequestManager & {
    enqueuedRequests: RequestEvent[];
    userEvents: unknown[];
  };
  setErrors: ReturnType<typeof vi.fn>;
  setMode: ReturnType<typeof vi.fn>;
  setLabelGroupViews: (views: LabelGroupView[]) => void;
  setActiveLabelGroupId: (id: ProvisionalId | null) => void;
  getMode: () => "edit" | "label" | "view";
  getGroupId: (name?: string) => ProvisionalId;
  labelGroupViews: LabelGroupView[];
  activeLabelGroupId: ProvisionalId | null;
};

function makeNovel(): Novel {
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

function makeChapter(): Chapter {
  return {
    chapterId: "chapter-1",
    chapterNum: 1,
    chapterTitle: "Arrival",
    chapterIsPublic: false,
    novelId: "novel-1",
  };
}

function makeLabel(
  labelId: string,
  labelDataId: string,
  labelStart: number,
  labelEnd: number,
  labelWord: string,
  labelEntityGroup: string | null = "character",
): Label {
  return {
    labelId,
    labelDataId,
    labelStart,
    labelEnd,
    labelWord,
    labelEntityGroup,
    labelScore: 1,
    labelDirty: false,
  };
}

function makeEditChapterData(role: "owner" | "editor" | "viewer" = "owner"): EditChapterData {
  const chapter = makeChapter();
  return {
    chapter,
    chapterContent: {
      chapterContentId: "content-1",
      chapterContentText: "Alice met Bob.",
      chapterContentVersion: 3,
    },
    role,
    labelGroupList: [
      {
        labelGroup: {
          labelGroupId: "group-characters",
          labelGroupName: "Characters",
          novelId: "novel-1",
        },
        labelData: {
          labelDataId: "label-data-characters",
          labelGroupId: "group-characters",
          chapterContentId: "content-1",
        },
        role,
      },
    ],
    labelDataList: [
      {
        labelDataId: "label-data-characters",
        labels: [
          makeLabel("label-alice", "label-data-characters", 0, 5, "Alice"),
          makeLabel("label-bob", "label-data-characters", 10, 13, "Bob"),
        ],
      },
    ],
  };
}

function makeRequestManager(): Harness["requestManager"] {
  let signalHandler: (signal: Signal) => void = () => {};
  const requestManager: Harness["requestManager"] & { emitSignal: (signal: Signal) => void } = {
    enqueuedRequests: [],
    userEvents: [],
    isQueueEmpty: () => requestManager.enqueuedRequests.length === 0,
    enqueueRequest: vi.fn((request: RequestEvent) => {
      requestManager.enqueuedRequests.push(request);
    }),
    handleSignal: vi.fn(),
    onUserEvent: vi.fn((event: unknown) => {
      requestManager.userEvents.push(event);
    }),
    send: vi.fn(async () => null),
    start: vi.fn(async () => undefined),
    attachControllerSignalHandler: vi.fn((handler: (signal: Signal) => void) => {
      signalHandler = handler;
    }),
    detachControllerSignalHandler: vi.fn(() => {
      signalHandler = () => {};
    }),
    waitFlush: vi.fn(async () => {
      requestManager.enqueuedRequests.length = 0;
    }),
    emitSignal: (signal: Signal) => {
      signalHandler(signal);
    },
  };
  return requestManager;
}

function renderController(role: "owner" | "editor" | "viewer" = "owner"): Harness {
  let mode: "edit" | "label" | "view" = "view";
  const editChapterData = makeEditChapterData(role);
  const setErrors = vi.fn();
  const setMode = vi.fn((nextMode: "edit" | "label" | "view") => {
    mode = nextMode;
  });
  const getMode = () => mode;
  const runtime = buildRuntime(
    setErrors,
    makeNovel(),
    editChapterData.chapter,
    editChapterData,
    "user-1",
  );
  const requestManager = makeRequestManager();
  const runtimeWithFakeRequests: Runtime = {
    ...runtime,
    requestManager,
  };

  let labelGroupViews: LabelGroupView[] = [];
  const setLabelGroupViews = (views: LabelGroupView[]) => {
    labelGroupViews = views;
  };
  let activeLabelGroupId: ProvisionalId | null = null;
  const setActiveLabelGroupId = (id: ProvisionalId | null) => {
    activeLabelGroupId = id;
  };

  const controller = buildController(
    editChapterData,
    getMode,
    setMode,
    runtimeWithFakeRequests,
    setErrors,
    setLabelGroupViews,
    setActiveLabelGroupId,
  );
  controller.start();

  return {
    controller,
    runtime: runtimeWithFakeRequests,
    requestManager,
    setErrors,
    setMode,
    setLabelGroupViews,
    setActiveLabelGroupId,
    getMode,
    get labelGroupViews() {
      return labelGroupViews;
    },
    get activeLabelGroupId() {
      return activeLabelGroupId;
    },
    getGroupId: (name = "Characters") => {
      const group = runtimeWithFakeRequests.dataManager
        .getGroups()
        .find((candidate) => candidate.labelGroupName === name);
      if (!group) {
        throw new Error(`Group '${name}' not found`);
      }
      return group.labelGroupId;
    },
  };
}

function labelSummaries(runtime: Runtime, labelGroupId: ProvisionalId) {
  return runtime.dataManager.getForGroup.labels(labelGroupId).map((label) => ({
    word: label.labelWord,
    start: label.labelStart,
    end: label.labelEnd,
    entityGroup: label.labelEntityGroup,
    dirty: label.labelDirty,
  }));
}

function labelByWord(runtime: Runtime, labelGroupId: ProvisionalId, word: string) {
  const label = runtime.dataManager.getForGroup
    .labels(labelGroupId)
    .find((candidate) => candidate.labelWord === word);
  if (!label) {
    throw new Error(`Label '${word}' not found`);
  }
  return label;
}

describe("edit controller", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("builds label group views from the runtime state", () => {
    const harness = renderController();
    const groupId = harness.getGroupId();

    expect(harness.labelGroupViews).toEqual([
      {
        labelGroupId: groupId,
        labelGroupName: "Characters",
        role: "owner",
        loadingStatus: "loaded",
        visible: true,
        color: expect.any(Number),
      },
    ]);
    expect(harness.activeLabelGroupId).toBeNull();
    expect(harness.runtime.uiManager.segmentManager.getText()).toBe("Alice met Bob.");
  });

  it("keeps data manager and segment manager coherent through mixed text, label, and group events", () => {
    const harness = renderController();
    const groupId = harness.getGroupId();

    harness.controller.handleEvent({ eventType: "switchMode", mode: "edit" });
    harness.controller.handleEvent({
      eventType: "textOp",
      op: { op: "insert", start: 6, text: "brave " },
    });
    expect(harness.runtime.uiManager.segmentManager.getText()).toBe("Alice brave met Bob.");
    expect(labelSummaries(harness.runtime, groupId)).toEqual([
      { word: "Alice", start: 0, end: 5, entityGroup: "character", dirty: false },
      { word: "Bob", start: 16, end: 19, entityGroup: "character", dirty: false },
    ]);

    harness.controller.handleEvent({ eventType: "switchMode", mode: "label" });
    expect(harness.requestManager.enqueuedRequests.map((request) => request.variant)).toEqual([
      "textOp",
    ]);

    harness.controller.handleEvent({ eventType: "switchLabelGroup", labelGroupId: groupId });
    expect(harness.activeLabelGroupId).toBe(groupId);

    harness.controller.handleEvent({
      eventType: "labelOp",
      labelGroupId: groupId,
      op: {
        op: "add",
        startPos: 6,
        endPos: 11,
        word: "brave",
        entityGroup: "trait",
        score: 0.8,
        dirty: true,
      },
    });
    const braveLabel = labelByWord(harness.runtime, groupId, "brave");
    expect(
      harness.runtime.uiManager.segmentManager.getLabel(braveLabel.labelId).style[1],
    ).toMatchObject({
      active: true,
      mutable: true,
      visible: true,
    });

    harness.controller.handleEvent({
      eventType: "labelOp",
      labelGroupId: groupId,
      op: {
        op: "update",
        startPos: 16,
        endPos: 19,
        word: "Bob",
        newStartPos: 16,
        newEndPos: 20,
        newWord: "Bob.",
        entityGroup: "character",
        score: 0.95,
        dirty: true,
      },
    });

    harness.controller.handleEvent({ eventType: "addLabelGroup", labelGroupName: "Places" });

    expect(labelSummaries(harness.runtime, groupId)).toEqual([
      { word: "Alice", start: 0, end: 5, entityGroup: "character", dirty: false },
      { word: "brave", start: 6, end: 11, entityGroup: "trait", dirty: true },
      { word: "Bob.", start: 16, end: 20, entityGroup: "character", dirty: true },
    ]);
    expect(harness.runtime.uiManager.segmentManager.getText()).toBe("Alice brave met Bob.");

    expect(harness.labelGroupViews.map((view) => view.labelGroupName)).toEqual([
      "Places",
      "Characters",
    ]);
    expect(harness.requestManager.enqueuedRequests.map((request) => request.variant)).toEqual([
      "textOp",
      "labelOp",
      "addLabelGroup",
      "addLabelGroup",
    ]);
  });

  it("updates visible label styles for active, clicked, hovered, and hidden groups", () => {
    const harness = renderController();
    const groupId = harness.getGroupId();
    const alice = labelByWord(harness.runtime, groupId, "Alice");
    const bob = labelByWord(harness.runtime, groupId, "Bob");

    harness.controller.handleEvent({ eventType: "switchMode", mode: "label" });
    harness.controller.handleEvent({ eventType: "switchLabelGroup", labelGroupId: groupId });
    expect(harness.runtime.uiManager.segmentManager.getLabel(alice.labelId).style[1].active).toBe(
      true,
    );
    expect(harness.runtime.uiManager.segmentManager.getLabel(bob.labelId).style[1].active).toBe(
      true,
    );

    harness.controller.handleEvent({ eventType: "clickPos", pos: 1 });
    expect(
      harness.runtime.uiManager.segmentManager.getLabel(alice.labelId).style[1].cursorStatus,
    ).toBe("clicked");
    expect(
      harness.runtime.uiManager.segmentManager.getLabel(bob.labelId).style[1].cursorStatus,
    ).toBe("none");

    harness.controller.handleEvent({ eventType: "hoverPos", pos: 11 });
    expect(
      harness.runtime.uiManager.segmentManager.getLabel(alice.labelId).style[1].cursorStatus,
    ).toBe("clicked");
    expect(
      harness.runtime.uiManager.segmentManager.getLabel(bob.labelId).style[1].cursorStatus,
    ).toBe("hovered");

    harness.controller.handleEvent({
      eventType: "toggleVisibility",
      labelGroupId: groupId,
      visible: false,
    });
    expect(harness.runtime.uiManager.segmentManager.getLabel(alice.labelId).style[1].visible).toBe(
      false,
    );
    expect(harness.runtime.uiManager.segmentManager.getLabel(bob.labelId).style[1].visible).toBe(
      false,
    );

    expect(harness.labelGroupViews[0].visible).toBe(false);
  });

  it("reports permission and mode errors without mutating editor state", () => {
    const harness = renderController("viewer");
    const groupId = harness.getGroupId();

    harness.controller.handleEvent({ eventType: "switchMode", mode: "edit" });
    expect(harness.setMode).not.toHaveBeenCalledWith("edit");
    expect(harness.setErrors).toHaveBeenCalledWith([
      expect.objectContaining({
        message: "You do not have permission to switch to edit mode",
      }),
    ]);

    harness.controller.handleEvent({
      eventType: "labelOp",
      labelGroupId: groupId,
      op: {
        op: "add",
        startPos: 6,
        endPos: 9,
        word: "met",
      },
    });
    expect(harness.setErrors).toHaveBeenCalledWith([
      expect.objectContaining({
        message: "Received label operation event while not in label mode",
      }),
    ]);
    expect(labelSummaries(harness.runtime, groupId)).toEqual([
      { word: "Alice", start: 0, end: 5, entityGroup: "character", dirty: false },
      { word: "Bob", start: 10, end: 13, entityGroup: "character", dirty: false },
    ]);
    expect(harness.runtime.uiManager.segmentManager.getText()).toBe("Alice met Bob.");
  });
});
