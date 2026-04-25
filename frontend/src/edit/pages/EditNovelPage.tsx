import { makeBasicSegmentManager } from "@/components/labeled-text-lib/core/segmentManager";
import { useMemo, useState } from "react";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import type { ColorStyle } from "@/components/labeled-text-lib/builtin/reducers";
import { makePlainBoxRenderer } from "@/components/labeled-text-lib/react/Renderer";
import type { Label, LabelGroup, LabelData } from "@/types/label";
import { toHex } from "@/components/labeled-text-lib/builtin/colors";
import { useParams, useSearchParams } from "react-router-dom";
import { extractParams } from "@/routes";


export function EditNovelPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const chapterId = useMemo(() => {
        return extractParams.edit.novel(searchParams).chapterId;
    }, [searchParams]);
    const novelId = useParams<"novelId">();
    const [activeLabelGroup, setActiveLabelGroup] = useState<LabelGroup | null>(null);
    const [labelDataMap, setLabelDataMap] = useState<Record<string, LabelData>>({});
    const [labelsMap, setLabelsMap] = useState<Record<string, Label[]>>({});
    const renderer = makePlainBoxRenderer<ColorStyle, StyledLabel<ColorStyle>>((style) => ({
        backgroundColor: toHex(style.color),
        display: "inline-block",
        width: "100%",
        height: "100%",
    }));
}