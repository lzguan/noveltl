import { useCallback, useEffect, useRef, useState } from "react";
import {
	AlertCircleIcon,
	CheckCircle2Icon,
	ExternalLinkIcon,
	GlobeIcon,
	KeyRoundIcon,
	LoaderCircleIcon,
	PencilIcon,
	PlugZapIcon,
	PlusIcon,
	Trash2Icon,
	UsersIcon,
} from "lucide-react";

import {
	readPublishingTargetsPublishingTargetsGet,
	testPublishingTargetPublishingTargetsTargetIdTestPost,
} from "@/api/endpoints/publishing/publishing";
import {
	TargetRole,
	type PublishingTargetRead,
	type PublishingTargetTestResult,
} from "@/api/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardAction,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { DeletePublishingTargetDialog } from "./DeletePublishingTargetDialog";
import { PublishingTargetFormDialog } from "./PublishingTargetFormDialog";
import { TargetMembersDialog } from "./TargetMembersDialog";

type TargetTestState =
	| { status: "testing" }
	| { status: "success"; result: PublishingTargetTestResult }
	| { status: "error"; message: string };

function TargetsSkeleton() {
	return (
		<div className="space-y-3">
			{Array.from({ length: 2 }).map((_, i) => (
				<div key={i} className="space-y-2 rounded-lg border p-4">
					<Skeleton className="h-5 w-48" />
					<Skeleton className="h-4 w-72" />
					<Skeleton className="h-4 w-56" />
				</div>
			))}
		</div>
	);
}

type FetchTargetsResult = { ok: true; data: PublishingTargetRead[] } | { ok: false; error: string };

async function requestPublishingTargets(signal: AbortSignal): Promise<FetchTargetsResult> {
	try {
		const resp = await readPublishingTargetsPublishingTargetsGet({ signal });
		if (resp.status !== 200) {
			return {
				ok: false,
				error: apiErrorMessage(resp.data, "Could not load publishing targets."),
			};
		}
		return { ok: true, data: resp.data };
	} catch (err: unknown) {
		return { ok: false, error: requestErrorMessage(err) };
	}
}

export function PublishingTargetsSection() {
	const [targets, setTargets] = useState<PublishingTargetRead[]>([]);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const targetsControllerRef = useRef<AbortController | null>(null);

	const [addOpen, setAddOpen] = useState(false);
	const [editingTarget, setEditingTarget] = useState<PublishingTargetRead | null>(null);
	const [membersTarget, setMembersTarget] = useState<PublishingTargetRead | null>(null);
	const [deletingTarget, setDeletingTarget] = useState<PublishingTargetRead | null>(null);
	const [testStates, setTestStates] = useState<Record<string, TargetTestState>>({});

	const applyTargetsResult = useCallback((result: FetchTargetsResult) => {
		if (!result.ok) {
			setLoadError(result.error);
		} else {
			setTargets(result.data);
			setLoadError(null);
		}
		setLoading(false);
	}, []);

	const retryLoadTargets = useCallback(() => {
		targetsControllerRef.current?.abort();
		const controller = new AbortController();
		targetsControllerRef.current = controller;
		setLoading(true);
		void requestPublishingTargets(controller.signal).then((result) => {
			if (!controller.signal.aborted) applyTargetsResult(result);
		});
	}, [applyTargetsResult]);

	useEffect(() => {
		const controller = new AbortController();
		targetsControllerRef.current = controller;
		void requestPublishingTargets(controller.signal).then((result) => {
			if (!controller.signal.aborted) applyTargetsResult(result);
		});
		return () => {
			targetsControllerRef.current?.abort();
		};
	}, [applyTargetsResult]);

	async function handleTestTarget(target: PublishingTargetRead) {
		setTestStates((current) => ({
			...current,
			[target.targetId]: { status: "testing" },
		}));
		try {
			const resp = await testPublishingTargetPublishingTargetsTargetIdTestPost(
				target.targetId,
			);
			if (resp.status !== 200) {
				setTestStates((current) => ({
					...current,
					[target.targetId]: {
						status: "error",
						message: apiErrorMessage(resp.data, "Connection test failed."),
					},
				}));
				return;
			}
			setTestStates((current) => ({
				...current,
				[target.targetId]: { status: "success", result: resp.data },
			}));
			if (resp.data.publicBaseUrl && resp.data.publicBaseUrl !== target.publicBaseUrl) {
				setTargets((current) =>
					current.map((item) =>
						item.targetId === target.targetId
							? { ...item, publicBaseUrl: resp.data.publicBaseUrl }
							: item,
					),
				);
			}
		} catch (err: unknown) {
			setTestStates((current) => ({
				...current,
				[target.targetId]: { status: "error", message: requestErrorMessage(err) },
			}));
		}
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle>Publishing targets</CardTitle>
				<CardDescription>
					Connect Reader instances so you and your team can publish novels directly from
					the editor.
				</CardDescription>
				<CardAction>
					<Button size="sm" onClick={() => setAddOpen(true)}>
						<PlusIcon data-icon="inline-start" />
						Add target
					</Button>
				</CardAction>
			</CardHeader>

			<CardContent>
				{loading && <TargetsSkeleton />}

				{!loading && loadError !== null && (
					<Alert variant="destructive">
						<AlertCircleIcon />
						<AlertDescription className="flex flex-wrap items-center justify-between gap-2">
							<span>{loadError}</span>
							<Button
								type="button"
								variant="outline"
								size="xs"
								onClick={retryLoadTargets}
							>
								Retry
							</Button>
						</AlertDescription>
					</Alert>
				)}

				{!loading && loadError === null && targets.length === 0 && (
					<Empty>
						<EmptyHeader>
							<EmptyTitle>No publishing targets configured</EmptyTitle>
							<EmptyDescription>
								Add a Reader instance with its publish API key to push novels and
								chapters from Studio.
							</EmptyDescription>
						</EmptyHeader>
						<EmptyContent>
							<Button onClick={() => setAddOpen(true)}>
								<PlusIcon data-icon="inline-start" />
								Add target
							</Button>
						</EmptyContent>
					</Empty>
				)}

				{!loading && loadError === null && targets.length > 0 && (
					<div className="space-y-3">
						{targets.map((target) => {
							const testState = testStates[target.targetId];
							const isOwner = target.role === TargetRole.owner;
							const isTesting = testState?.status === "testing";

							return (
								<article
									key={target.targetId}
									className="space-y-3 rounded-lg border bg-background p-4"
								>
									<div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
										<div className="min-w-0 space-y-1.5">
											<div className="flex flex-wrap items-center gap-2">
												<h3 className="truncate font-medium">
													{target.name}
												</h3>
												<Badge
													variant={isOwner ? "secondary" : "outline"}
													className="text-[11px]"
												>
													{target.role}
												</Badge>
											</div>

											<div className="flex flex-col gap-1 text-xs text-muted-foreground">
												<div className="flex items-center gap-1.5 break-all">
													<span className="font-medium text-foreground/80">
														API:
													</span>
													<code className="font-mono">
														{target.apiBaseUrl}
													</code>
												</div>

												{target.publicBaseUrl && (
													<div className="flex items-center gap-1.5 break-all">
														<GlobeIcon className="size-3.5 shrink-0" />
														<a
															href={target.publicBaseUrl}
															target="_blank"
															rel="noopener noreferrer"
															className="inline-flex items-center gap-1 underline underline-offset-4 hover:text-foreground"
														>
															{target.publicBaseUrl}
															<ExternalLinkIcon className="size-3 shrink-0" />
														</a>
													</div>
												)}

												<div className="flex items-center gap-1.5">
													<KeyRoundIcon className="size-3.5 shrink-0" />
													<span>API key:</span>
													<code className="font-mono">
														{target.keyPrefix}…
													</code>
												</div>
											</div>
										</div>

										<div className="flex flex-wrap items-center gap-1.5">
											<Button
												type="button"
												variant="outline"
												size="sm"
												disabled={isTesting}
												onClick={() => void handleTestTarget(target)}
											>
												{isTesting ? (
													<LoaderCircleIcon
														data-icon="inline-start"
														className="animate-spin"
													/>
												) : (
													<PlugZapIcon data-icon="inline-start" />
												)}
												{isTesting ? "Testing..." : "Test connection"}
											</Button>

											{isOwner && (
												<>
													<Button
														type="button"
														variant="outline"
														size="sm"
														onClick={() => setMembersTarget(target)}
													>
														<UsersIcon data-icon="inline-start" />
														Members
													</Button>
													<Button
														type="button"
														variant="outline"
														size="sm"
														onClick={() => setEditingTarget(target)}
													>
														<PencilIcon data-icon="inline-start" />
														Edit
													</Button>
													<Button
														type="button"
														variant="destructive"
														size="sm"
														onClick={() => setDeletingTarget(target)}
													>
														<Trash2Icon data-icon="inline-start" />
														Delete
													</Button>
												</>
											)}
										</div>
									</div>

									{testState?.status === "success" && (
										<div
											role="status"
											className="flex flex-wrap items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-300"
										>
											<CheckCircle2Icon className="size-3.5 shrink-0" />
											<span>
												Connected to{" "}
												<strong className="font-medium">
													{testState.result.name}
												</strong>
												{testState.result.publicBaseUrl ? (
													<> ({testState.result.publicBaseUrl})</>
												) : null}
											</span>
										</div>
									)}

									{testState?.status === "error" && (
										<Alert variant="destructive">
											<AlertCircleIcon />
											<AlertDescription>{testState.message}</AlertDescription>
										</Alert>
									)}
								</article>
							);
						})}
					</div>
				)}
			</CardContent>

			{addOpen && (
				<PublishingTargetFormDialog
					mode="create"
					onSaved={(created) => {
						setTargets((current) => [
							created,
							...current.filter((item) => item.targetId !== created.targetId),
						]);
						setLoadError(null);
					}}
					onClose={() => setAddOpen(false)}
				/>
			)}

			{editingTarget !== null && (
				<PublishingTargetFormDialog
					key={editingTarget.targetId}
					mode="edit"
					target={editingTarget}
					onSaved={(updated) => {
						setTargets((current) =>
							current.map((item) =>
								item.targetId === updated.targetId ? updated : item,
							),
						);
						setTestStates((current) => {
							const next = { ...current };
							delete next[updated.targetId];
							return next;
						});
					}}
					onClose={() => setEditingTarget(null)}
				/>
			)}

			{membersTarget !== null && (
				<TargetMembersDialog
					key={membersTarget.targetId}
					target={membersTarget}
					onClose={() => setMembersTarget(null)}
				/>
			)}

			{deletingTarget !== null && (
				<DeletePublishingTargetDialog
					key={deletingTarget.targetId}
					target={deletingTarget}
					onDeleted={(targetId) => {
						setTargets((current) =>
							current.filter((item) => item.targetId !== targetId),
						);
					}}
					onClose={() => setDeletingTarget(null)}
				/>
			)}
		</Card>
	);
}
