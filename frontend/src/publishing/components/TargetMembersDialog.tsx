import { useEffect, useState, type SubmitEvent } from "react";
import { AlertCircleIcon, Trash2Icon, UserPlusIcon } from "lucide-react";

import {
	deletePublishingTargetMemberPublishingTargetsTargetIdMembersUserIdDelete,
	readPublishingTargetMembersPublishingTargetsTargetIdMembersGet,
	upsertPublishingTargetMemberPublishingTargetsTargetIdMembersPost,
} from "@/api/endpoints/publishing/publishing";
import {
	TargetRole,
	type PublishingTargetMemberRead,
	type PublishingTargetRead,
} from "@/api/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";

function targetRoleFromValue(value: string): TargetRole {
	return value === TargetRole.owner ? TargetRole.owner : TargetRole.publisher;
}

function useAddMemberForm() {
	const [userName, setUserName] = useState("");
	const [role, setRole] = useState<TargetRole>(TargetRole.publisher);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	function startSubmit() {
		setSubmitting(true);
		setError(null);
	}

	function submitSuccess() {
		setSubmitting(false);
		setError(null);
		setUserName("");
		setRole(TargetRole.publisher);
	}

	function submitFailure(message: string) {
		setSubmitting(false);
		setError(message);
	}

	return {
		userName,
		setUserName,
		role,
		setRole,
		submitting,
		error,
		startSubmit,
		submitSuccess,
		submitFailure,
	};
}

export function TargetMembersDialog({
	target,
	onClose,
}: {
	target: PublishingTargetRead;
	onClose: () => void;
}) {
	const [members, setMembers] = useState<PublishingTargetMemberRead[]>([]);
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [removeError, setRemoveError] = useState<string | null>(null);
	const [removingUserId, setRemovingUserId] = useState<string | null>(null);

	const form = useAddMemberForm();

	useEffect(() => {
		const controller = new AbortController();
		let ignore = false;

		readPublishingTargetMembersPublishingTargetsTargetIdMembersGet(target.targetId, {
			signal: controller.signal,
		})
			.then((resp) => {
				if (ignore) return;
				if (resp.status !== 200) {
					setLoadError(apiErrorMessage(resp.data, "Could not load target members."));
					return;
				}
				setMembers(resp.data);
				setLoadError(null);
			})
			.catch((err: unknown) => {
				if (ignore || controller.signal.aborted) return;
				setLoadError(requestErrorMessage(err));
			})
			.finally(() => {
				if (!ignore) setLoading(false);
			});

		return () => {
			ignore = true;
			controller.abort();
		};
	}, [target.targetId]);

	async function handleAddMember(event: SubmitEvent<HTMLFormElement>) {
		event.preventDefault();
		if (form.submitting) return;

		const trimmedUserName = form.userName.trim();
		if (!trimmedUserName) {
			form.submitFailure("Username is required.");
			return;
		}

		setRemoveError(null);
		form.startSubmit();
		try {
			const resp = await upsertPublishingTargetMemberPublishingTargetsTargetIdMembersPost(
				target.targetId,
				{
					userName: trimmedUserName,
					role: form.role,
				},
			);
			if (resp.status !== 200) {
				form.submitFailure(apiErrorMessage(resp.data, "Could not save target member."));
				return;
			}
			setMembers((current) => {
				const exists = current.some((member) => member.userId === resp.data.userId);
				if (exists) {
					return current.map((member) =>
						member.userId === resp.data.userId ? resp.data : member,
					);
				}
				return [...current, resp.data];
			});
			form.submitSuccess();
		} catch (err: unknown) {
			form.submitFailure(requestErrorMessage(err));
		}
	}

	async function handleRemoveMember(member: PublishingTargetMemberRead) {
		if (removingUserId !== null) return;
		setRemovingUserId(member.userId);
		setRemoveError(null);
		try {
			const resp =
				await deletePublishingTargetMemberPublishingTargetsTargetIdMembersUserIdDelete(
					target.targetId,
					member.userId,
				);
			if (resp.status !== 200) {
				setRemoveError(apiErrorMessage(resp.data, "Could not remove member."));
				return;
			}
			setMembers((current) => current.filter((item) => item.userId !== member.userId));
		} catch (err: unknown) {
			setRemoveError(requestErrorMessage(err));
		} finally {
			setRemovingUserId(null);
		}
	}

	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open) onClose();
			}}
		>
			<DialogContent className="sm:max-w-lg">
				<DialogHeader>
					<DialogTitle>Share &ldquo;{target.name}&rdquo;</DialogTitle>
					<DialogDescription>
						Manage who can publish to or administer this Reader target.
					</DialogDescription>
				</DialogHeader>

				<form
					className="flex flex-col gap-3 rounded-lg border bg-muted/30 p-3"
					onSubmit={(e) => void handleAddMember(e)}
				>
					<div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto_auto] sm:items-end">
						<Field>
							<FieldLabel htmlFor="target-member-username">Username</FieldLabel>
							<Input
								id="target-member-username"
								placeholder="Enter username"
								value={form.userName}
								disabled={form.submitting}
								onChange={(e) => form.setUserName(e.target.value)}
							/>
						</Field>

						<Field>
							<FieldLabel htmlFor="target-member-role">Role</FieldLabel>
							<Select
								value={form.role}
								disabled={form.submitting}
								onValueChange={(value) => form.setRole(targetRoleFromValue(value))}
							>
								<SelectTrigger id="target-member-role" className="w-full sm:w-32">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value={TargetRole.publisher}>Publisher</SelectItem>
									<SelectItem value={TargetRole.owner}>Owner</SelectItem>
								</SelectContent>
							</Select>
						</Field>

						<Button type="submit" disabled={form.submitting}>
							<UserPlusIcon data-icon="inline-start" />
							{form.submitting ? "Saving..." : "Save"}
						</Button>
					</div>

					{form.error !== null && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertDescription>{form.error}</AlertDescription>
						</Alert>
					)}
				</form>

				{removeError !== null && (
					<Alert variant="destructive">
						<AlertCircleIcon />
						<AlertDescription>{removeError}</AlertDescription>
					</Alert>
				)}

				<div className="space-y-2">
					<h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
						Members
					</h3>

					{loading && (
						<div className="space-y-2">
							<Skeleton className="h-10 w-full" />
							<Skeleton className="h-10 w-full" />
						</div>
					)}

					{!loading && loadError !== null && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertDescription>{loadError}</AlertDescription>
						</Alert>
					)}

					{!loading && loadError === null && members.length === 0 && (
						<p className="text-sm text-muted-foreground">No members found.</p>
					)}

					{!loading && loadError === null && members.length > 0 && (
						<ul className="divide-y rounded-lg border">
							{members.map((member) => {
								const isRemoving = removingUserId === member.userId;
								return (
									<li
										key={member.userId}
										className="flex items-center justify-between gap-3 px-3 py-2"
									>
										<div className="flex min-w-0 items-center gap-2">
											<span className="truncate text-sm font-medium">
												{member.userName}
											</span>
											<Badge
												variant={
													member.role === TargetRole.owner
														? "secondary"
														: "outline"
												}
											>
												{member.role}
											</Badge>
										</div>
										<Button
											type="button"
											variant="ghost"
											size="sm"
											disabled={removingUserId !== null}
											aria-label={`Remove ${member.userName}`}
											onClick={() => void handleRemoveMember(member)}
										>
											<Trash2Icon className="size-3.5" />
											{isRemoving ? "Removing..." : "Remove"}
										</Button>
									</li>
								);
							})}
						</ul>
					)}
				</div>

				<DialogFooter>
					<Button type="button" variant="outline" onClick={onClose}>
						Done
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
