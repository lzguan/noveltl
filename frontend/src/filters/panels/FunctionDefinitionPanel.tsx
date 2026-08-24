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
import { apiErrorMessage, requestErrorMessage } from "../apiErrors";
import { FunctionDefinitionEditor } from "../components/FunctionDefinitionEditor";
import { FunctionSignatureDisplay } from "../components/FunctionSignatureDisplay";
import {
	parseFunctionDefinitionText,
	useFunctionDefinitionForm,
} from "../hooks/useFunctionDefinitionForm";

function FunctionDefinitionStatus({
	formStatus,
}: {
	formStatus: ReturnType<typeof useFunctionDefinitionForm>["formStatus"];
}) {
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

export function FunctionDefinitionPanel() {
	const props = useFunctionDefinitionForm();
	const pending =
		props.formStatus.status === "validating" || props.formStatus.status === "uploading";

	function readFunctionDefinition() {
		const parsed = parseFunctionDefinitionText(props.functionDefinitionText);
		if (!parsed.ok) {
			props.setFunctionDefinitionError(parsed.message);
			return null;
		}
		props.setFunctionDefinitionError(null);
		return parsed.definition;
	}

	async function validateFunctionDefinition() {
		const definition = readFunctionDefinition();
		if (definition === null) return;
		props.preSend("validate");
		try {
			const response = await validateFilterFunction({ functionDefinition: definition });
			if (response.status === 200) {
				props.onSendSuccess({ action: "validate", signature: response.data.signature });
			} else {
				props.onSendError(
					"validate",
					apiErrorMessage(response.data, "Function definition is invalid."),
				);
			}
		} catch (error) {
			props.onSendError("validate", requestErrorMessage(error));
		}
	}

	async function uploadFunctionDefinition() {
		const definition = readFunctionDefinition();
		if (definition === null) return;
		props.preSend("upload");
		try {
			const response = await createFilterFunction({
				functionDefinition: definition,
				functionName: props.functionName.trim(),
				namespace: props.functionNamespace.trim(),
			});
			if (response.status === 201) {
				props.onSendSuccess({ action: "upload", functionDefinition: response.data });
			} else {
				props.onSendError(
					"upload",
					apiErrorMessage(response.data, "Function definition could not be uploaded."),
				);
			}
		} catch (error) {
			props.onSendError("upload", requestErrorMessage(error));
		}
	}

	function submitFunctionDefinition(event: React.SubmitEvent<HTMLFormElement>) {
		event.preventDefault();
		void uploadFunctionDefinition();
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
							onClick={() => void validateFunctionDefinition()}
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
import { createFilterFunction, validateFilterFunction } from "@/api/endpoints/filters/filters";
