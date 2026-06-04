import {
  DynamicLabeledText,
  type Caret,
} from "@/components/labeled-text-lib/react/DynamicLabeledText";
import type { Controller, EditorMode, MyStyle } from "../controller/types";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import { useState } from "react";
import type { Label, LabelGroup } from "@/client";
import type { Color } from "@/components/labeled-text-lib/builtin/colors";
import type { SegmentManager } from "@/components/labeled-text-lib/core/segmentManager";
import { makePlainBoxRenderer } from "@/components/labeled-text-lib/react/Renderer";

type LabelAndGroup = {
  label: Label;
  labelGroup: LabelGroup;
  colour: Color;
};

type LabelPopupProps = {
  labels: LabelAndGroup[];
};

function LabelContextMenu(props: LabelPopupProps) {
  return <></>;
}

function EditorComponent({
  controller,
  manager,
  getMode,
  setMode,
}: {
  controller: Controller;
  manager: SegmentManager<MyStyle, StyledLabel<MyStyle>>;
  getMode: () => EditorMode;
  setMode: (mode: EditorMode) => void;
}) {
  const [caret, setCaret] = useState<Caret>({
    anchor: 0,
    focus: 0,
    visible: false,
  });

  return (
    <div>
      <DynamicLabeledText
        caret={caret}
        manager={manager}
        render={{
          ...makePlainBoxRenderer<MyStyle, StyledLabel<MyStyle>>((style) => ({
            backgroundColor: `${style[0]}28`,
            border: `1px solid ${style[0]}5c`,
            borderRadius: "0.45rem",
          })),
          renderCaret: () => {
            // finish later
            return <></>;
          },
        }}
      />
    </div>
  );
}

export { EditorComponent };
