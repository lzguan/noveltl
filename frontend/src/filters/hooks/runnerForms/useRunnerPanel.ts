import { useState } from "react";
import type { RunnerOperation, RunnerPanelModel } from "../../types";
import { useFilterRunnerForm } from "./useFilterRunnerForm";
import { useGroupRunnerForm } from "./useGroupRunnerForm";
import { useLabelSourceRunnerForm } from "./useLabelSourceRunnerForm";
import { useMapRunnerForm } from "./useMapRunnerForm";

export function useRunnerPanel(novelId: string, enabled: boolean): RunnerPanelModel {
	const [activeRunnerOperation, setActiveRunnerOperation] =
		useState<RunnerOperation>("labelSource");
	const labelSourceForm = useLabelSourceRunnerForm(
		novelId,
		enabled && activeRunnerOperation === "labelSource",
	);
	const mapForm = useMapRunnerForm(novelId, enabled && activeRunnerOperation === "map");
	const filterForm = useFilterRunnerForm(novelId, enabled && activeRunnerOperation === "filter");
	const groupForm = useGroupRunnerForm(novelId, enabled && activeRunnerOperation === "group");

	return {
		activeRunnerOperation,
		labelSourceForm,
		mapForm,
		filterForm,
		groupForm,
		selectRunnerOperation: setActiveRunnerOperation,
	};
}
