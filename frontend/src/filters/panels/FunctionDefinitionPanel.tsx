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
import { CircleCheck, TriangleAlert } from "lucide-react";
import { FunctionDefinitionEditor } from "../components/FunctionDefinitionEditor";
import { FunctionSignatureDisplay } from "../components/FunctionSignatureDisplay";
import type { FunctionDefinitionFormModel } from "../types";

function FunctionDefinitionStatus({ formStatus }: Pick<FunctionDefinitionFormModel, "formStatus">) {
	if (
		formStatus.status === "idle" ||
		formStatus.status === "validating" ||
		formStatus.status === "uploading"
	) {
		return null;
	}
	if (formStatus.status === "error") {
		return (
			<Alert variant="destructive">
				<TriangleAlert />
				<AlertTitle>
					{formStatus.action === "validate" ? "Validation failed" : "Upload failed"}
				</AlertTitle>
				<AlertDescription>{formStatus.message}</AlertDescription>
			</Alert>
		);
	}
	if (formStatus.status === "uploaded") {
		const definition = formStatus.functionDefinition;
		return (
			<Alert>
				<CircleCheck />
				<AlertTitle>Function uploaded</AlertTitle>
				<AlertDescription>
					{definition.namespace}.{definition.functionName} ·{" "}
					{definition.functionDefinitionId}
				</AlertDescription>
			</Alert>
		);
	}

	return (
		<div className="flex min-w-0 flex-col gap-3">
			<Alert>
				<CircleCheck />
				<AlertTitle>Function is valid</AlertTitle>
				<AlertDescription>
					Review the computed input and output types below.
				</AlertDescription>
			</Alert>
			<FunctionSignatureDisplay signature={formStatus.signature} />
		</div>
	);
}

export function FunctionDefinitionPanel(props: FunctionDefinitionFormModel) {
	const pending =
		props.formStatus.status === "validating" || props.formStatus.status === "uploading";

	function submitFunctionDefinition(event: React.SubmitEvent<HTMLFormElement>) {
		event.preventDefault();
		void props.uploadFunctionDefinition();
	}

	return (
		<section
			className="flex min-w-0 flex-col gap-4"
			aria-labelledby="function-definition-title"
		>
			<form onSubmit={submitFunctionDefinition}>
				<Card>
					<CardHeader>
						<CardTitle id="function-definition-title">Function library</CardTitle>
						<CardDescription>
							Validate a serialized function locally on the backend, then save it to
							the shared library.
						</CardDescription>
					</CardHeader>
					<CardContent>
						<FunctionDefinitionEditor
							functionNamespace={props.functionNamespace}
							functionName={props.functionName}
							functionDefinitionText={props.functionDefinitionText}
							functionDefinitionError={props.functionDefinitionError}
							disabled={pending}
							setFunctionNamespace={props.setFunctionNamespace}
							setFunctionName={props.setFunctionName}
							setFunctionDefinitionText={props.setFunctionDefinitionText}
						/>
					</CardContent>
					<CardFooter className="justify-end gap-2 border-t">
						<Button
							type="button"
							variant="outline"
							disabled={pending}
							onClick={() => void props.validateFunctionDefinition()}
						>
							{props.formStatus.status === "validating" ? "Validating…" : "Validate"}
						</Button>
						<Button type="submit" disabled={pending}>
							{props.formStatus.status === "uploading" ? "Uploading…" : "Upload"}
						</Button>
					</CardFooter>
				</Card>
			</form>
			<FunctionDefinitionStatus formStatus={props.formStatus} />
		</section>
	);
}
