import { readMemoryGroupsMemoryGroupsGet } from "@/api/endpoints/default/default";
import type { MemoryGroup } from "@/api/models";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import type { Loadable } from "@/lib/loadable";
import { useCallback, useRef, useState } from "react";

/** Owns lazy loading, selection, and insertion for a novel's memory groups. */
export function useMemoryGroups(novelId: string) {
	const [groups, setGroups] = useState<Loadable<readonly MemoryGroup[]>>({ status: "idle" });
	const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
	const activeRequest = useRef<AbortController | null>(null);

	const loadGroups = useCallback(() => {
		activeRequest.current?.abort();
		const controller = new AbortController();
		activeRequest.current = controller;
		setGroups({ status: "loading" });

		void readMemoryGroupsMemoryGroupsGet({ novelId }, { signal: controller.signal })
			.then((response) => {
				if (controller.signal.aborted) return;
				if (response.status !== 200) {
					setGroups({
						status: "error",
						message: apiErrorMessage(response.data, "Could not load memory groups."),
					});
					return;
				}

				setGroups({ status: "ready", data: response.data });
				setSelectedGroupId((current) =>
					current !== null &&
					response.data.some((group) => group.memoryGroupId === current)
						? current
						: (response.data[0]?.memoryGroupId ?? null),
				);
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted) {
					setGroups({ status: "error", message: requestErrorMessage(error) });
				}
			})
			.finally(() => {
				if (activeRequest.current === controller) activeRequest.current = null;
			});
	}, [novelId]);

	const selectGroup = useCallback((memoryGroupId: string) => {
		setSelectedGroupId(memoryGroupId);
	}, []);

	const addAndSelectGroup = useCallback((group: MemoryGroup) => {
		setGroups((current) => ({
			status: "ready",
			data:
				current.status === "ready"
					? [
							...current.data.filter(
								(existing) => existing.memoryGroupId !== group.memoryGroupId,
							),
							group,
						]
					: [group],
		}));
		setSelectedGroupId(group.memoryGroupId);
	}, []);

	return {
		groups,
		selectedGroupId,
		loadGroups,
		reloadGroups: loadGroups,
		selectGroup,
		addAndSelectGroup,
	};
}
