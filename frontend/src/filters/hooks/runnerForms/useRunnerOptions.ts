import { readLabelGroupsLabelGroupsGet } from "@/api/endpoints/default/default";
import {
	readFunctionsFiltersFunctionsGet,
	readWorkflowsFiltersWorkflowsGet,
} from "@/api/endpoints/filters/filters";
import type { FunctionDefinitionMeta, LabelGroup, WorkflowSummary } from "@/api/models";
import { useEffect, useState } from "react";
import { apiErrorMessage, requestErrorMessage } from "../../apiErrors";
import type { Loadable } from "../../loadable";

export async function fetchCompletedWorkflowOptions(
	novelId: string,
	keyword: string,
	signal: AbortSignal,
): Promise<readonly WorkflowSummary[]> {
	const response = await readWorkflowsFiltersWorkflowsGet(
		{ novelId, status: "complete", search: keyword || undefined, limit: 100 },
		{ signal },
	);
	if (response.status !== 200) {
		throw new Error(apiErrorMessage(response.data, "Could not load completed workflows."));
	}
	return response.data;
}

export async function fetchFunctionDefinitionOptions(
	keyword: string,
	signal: AbortSignal,
): Promise<readonly FunctionDefinitionMeta[]> {
	const response = await readFunctionsFiltersFunctionsGet(
		{ search: keyword || undefined, limit: 100 },
		{ signal },
	);
	if (response.status !== 200) {
		throw new Error(apiErrorMessage(response.data, "Could not load function definitions."));
	}
	return response.data;
}

export function useLabelGroupOptions(novelId: string, enabled: boolean) {
	const [labelGroups, setLabelGroups] = useState<Loadable<readonly LabelGroup[]>>({
		status: "idle",
	});

	useEffect(() => {
		if (!enabled) return;

		const controller = new AbortController();
		// This state transition intentionally coincides with starting the request.
		// eslint-disable-next-line react-hooks/set-state-in-effect
		setLabelGroups({ status: "loading" });
		void readLabelGroupsLabelGroupsGet({ novelId }, { signal: controller.signal })
			.then((response) => {
				if (controller.signal.aborted) return;
				if (response.status === 200) {
					setLabelGroups({ status: "ready", data: response.data });
				} else {
					setLabelGroups({
						status: "error",
						message: apiErrorMessage(response.data, "Could not load label groups."),
					});
				}
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted)
					setLabelGroups({ status: "error", message: requestErrorMessage(error) });
			});

		return () => controller.abort();
	}, [enabled, novelId]);

	return labelGroups;
}
