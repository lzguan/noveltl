import type { Signature } from "@/api/models";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowRight } from "lucide-react";
import { SObjDisplay } from "./SObjDisplay";

export function FunctionSignatureDisplay({ signature }: { signature: Signature }) {
	const args = signature.args ?? [];

	return (
		<section
			aria-label="Function signature"
			className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3"
		>
			<div className="flex min-w-0 flex-col gap-3">
				<div className="text-sm font-medium">Inputs</div>
				{args.length === 0 ? (
					<Card size="sm">
						<CardHeader>
							<CardTitle>Arguments</CardTitle>
							<CardDescription>No arguments</CardDescription>
						</CardHeader>
					</Card>
				) : (
					args.map((argument, index) => (
						<SObjDisplay key={index} label={`Argument ${index + 1}`} value={argument} />
					))
				)}
			</div>

			<ArrowRight aria-hidden="true" />

			<div className="flex min-w-0 flex-col gap-3">
				<div className="text-sm font-medium">Output</div>
				<SObjDisplay label="Return value" value={signature.output} />
			</div>
		</section>
	);
}
