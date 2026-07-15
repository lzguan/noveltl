import { CodeMirrorEditor } from "./editor/CodeMirrorEditor";
import type { Caret } from "../hooks/useEditorState";
import type { EditorMode } from "../managers/editorManager";
import type { EditorData } from "../hooks/useEditorState";
import type { TextOp } from "@/api/models";
import type { LabelEditing } from "../labeling/types";
import type { AutoLabelPreview } from "../hooks/useAutoLabelPreview";

export function EditorPanel({
	data,
	mode,
	onSetCaret,
	onTextOp,
	labeling,
	preview,
}: {
	data: EditorData;
	mode: EditorMode;
	onSetCaret: (c: Caret | null) => void;
	onTextOp: (op: TextOp) => void;
	labeling: LabelEditing;
	preview: AutoLabelPreview | null;
}) {
	if (data.empty) {
		return (
			<div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
				No chapter selected
			</div>
		);
	}
	if (data.loading) {
		return (
			<div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
				Loading...
			</div>
		);
	}
	return (
		<div className="flex-1 overflow-hidden">
			<CodeMirrorEditor
				key={data.chapterId}
				sm={data.segmentManager}
				mode={mode}
				onSetCaret={onSetCaret}
				onTextOp={onTextOp}
				labeling={labeling}
				preview={preview}
			/>
		</div>
	);
}
