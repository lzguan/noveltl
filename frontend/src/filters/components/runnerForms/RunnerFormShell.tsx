import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { FieldGroup } from "@/components/ui/field";
import { CircleCheck, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import type { RunnerFormStatus } from "../../types";

function RunnerOperationStatus({ formStatus }: { formStatus: RunnerFormStatus }) {
	if (formStatus.status === "idle" || formStatus.status === "submitting") return null;
	if (formStatus.status === "error") {
		return (
			<Alert variant="destructive">
				<TriangleAlert />
				<AlertTitle>Runner request failed</AlertTitle>
				<AlertDescription>{formStatus.message}</AlertDescription>
			</Alert>
		);
	}
	return (
		<Alert>
			<CircleCheck />
			<AlertTitle>
				{formStatus.target === "workflow"
					? "Workflow created and queued"
					: "Grouping created and queued"}
			</AlertTitle>
			<AlertDescription>
				{formStatus.target === "workflow"
					? "The operation was accepted. Refresh the Viewer workflow list when needed."
					: "The operation was accepted. The grouping appears when its workflow is loaded again."}
			</AlertDescription>
		</Alert>
	);
}

export function RunnerFormShell({
	title,
	description,
	submitLabel,
	formStatus,
	canSubmit,
	submitRunnerOperation,
	children,
}: {
	title: string;
	description: string;
	submitLabel: string;
	formStatus: RunnerFormStatus;
	canSubmit: boolean;
	submitRunnerOperation: () => Promise<void>;
	children: ReactNode;
}) {
	const submitting = formStatus.status === "submitting";

	function submitForm(event: React.SubmitEvent<HTMLFormElement>) {
		event.preventDefault();
		void submitRunnerOperation();
	}

	return (
		<div className="flex min-w-0 flex-col gap-3">
			<form onSubmit={submitForm}>
				<Card>
					<CardHeader>
						<CardTitle>{title}</CardTitle>
						<CardDescription>{description}</CardDescription>
					</CardHeader>
					<CardContent>
						<FieldGroup>{children}</FieldGroup>
					</CardContent>
					<CardFooter className="justify-end border-t">
						<Button type="submit" disabled={!canSubmit || submitting}>
							{submitting ? "Creating…" : submitLabel}
						</Button>
					</CardFooter>
				</Card>
			</form>
			<RunnerOperationStatus formStatus={formStatus} />
		</div>
	);
}
