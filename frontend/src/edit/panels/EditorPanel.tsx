import { CodeMirrorEditor } from "./CodeMirrorEditor";
import type { Caret } from "@/components/labeled-text-lib/react/DynamicLabeledText";
import type { EditorMode } from "../managers/editorManager";
import type { IDLabelOp } from "../controller/types/dataTypes";
import type { EditorData } from "../hooks/useEditorState";
import type { TextOp } from "@/api/models";

export function EditorPanel({
	data,
	mode,
	onSetCaret,
	onTextOp,
	onLabelOp: _onLabelOp,
}: {
	data: EditorData;
	mode: EditorMode;
	onSetCaret: (c: Caret | null) => void;
	onTextOp: (op: TextOp) => void;
	onLabelOp: (op: IDLabelOp) => void;
}) {
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
			/>
		</div>
	);
}
