import { MemoryType, type GlossaryTerm, type Scope } from "@/api/models";
import { useState } from "react";

type FormStatus =
	| { status: "idle" }
	| { status: "submitting" }
	| { status: "succeeded" }
	| { status: "error"; message: string };

/** Owns the draft and request-state transitions for creating a new glossary memory. */
export function useGlossaryMemoryForm(initialTerms: readonly GlossaryTerm[] = []) {
	const [memoryContent, setMemoryContentState] = useState("");
	const [memoryType, setMemoryTypeState] = useState<MemoryType>(MemoryType.fact);
	const [scope, setScopeState] = useState<Scope | null>(null);
	const [selectedTerms, setSelectedTerms] = useState<readonly GlossaryTerm[]>(initialTerms);
	const [formStatus, setFormStatus] = useState<FormStatus>({ status: "idle" });

	function resetRequestStatus() {
		setFormStatus({ status: "idle" });
	}

	function setMemoryContent(memoryContent: string) {
		setMemoryContentState(memoryContent);
		resetRequestStatus();
	}

	function setMemoryType(memoryType: MemoryType) {
		setMemoryTypeState(memoryType);
		resetRequestStatus();
	}

	function setScope(scope: Scope | null) {
		setScopeState(scope);
		resetRequestStatus();
	}

	function setTermSelected(term: GlossaryTerm, selected: boolean) {
		setSelectedTerms((current) =>
			selected
				? current.some((candidate) => candidate.termId === term.termId)
					? current
					: [...current, term]
				: current.filter((candidate) => candidate.termId !== term.termId),
		);
		resetRequestStatus();
	}

	function preSend() {
		setFormStatus({ status: "submitting" });
	}

	function onSendError(message: string) {
		setFormStatus({ status: "error", message });
	}

	function onSendSuccess() {
		setFormStatus({ status: "succeeded" });
	}

	function resetForm() {
		setMemoryContentState("");
		setMemoryTypeState(MemoryType.fact);
		setScopeState(null);
		setSelectedTerms(initialTerms);
		setFormStatus({ status: "idle" });
	}

	return {
		memoryContent,
		memoryType,
		scope,
		selectedTerms,
		selectedTermIds: selectedTerms.map((term) => term.termId),
		formStatus,
		setMemoryContent,
		setMemoryType,
		setScope,
		setTermSelected,
		preSend,
		onSendError,
		onSendSuccess,
		resetForm,
	};
}
