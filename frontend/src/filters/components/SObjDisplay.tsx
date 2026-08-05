import type { SObj } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

export interface SObjDisplayProps {
	label: string;
	value: SObj;
}

export function SObjDisplay({ label, value }: SObjDisplayProps) {
	if (value.kind !== "schema") {
		return (
			<Card size="sm">
				<CardHeader>
					<CardTitle>{label}</CardTitle>
					<CardDescription>Elementary type</CardDescription>
				</CardHeader>
				<CardContent className="flex flex-wrap gap-2">
					<Badge variant="outline">{value.type}</Badge>
					{value.mutable && <Badge variant="secondary">Mutable</Badge>}
				</CardContent>
			</Card>
		);
	}

	const fields = Object.entries(value.fields ?? {});

	return (
		<Card size="sm">
			<CardHeader>
				<CardTitle>{label}</CardTitle>
				<CardDescription>
					Object schema · {fields.length} {fields.length === 1 ? "field" : "fields"}
				</CardDescription>
			</CardHeader>
			<CardContent className="px-0">
				<Table aria-label={`${label} fields`}>
					<TableHeader>
						<TableRow>
							<TableHead>Field name</TableHead>
							<TableHead>Type</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{fields.length === 0 ? (
							<TableRow>
								<TableCell colSpan={2} className="text-muted-foreground">
									No fields
								</TableCell>
							</TableRow>
						) : (
							fields.map(([fieldName, field]) => (
								<TableRow key={fieldName}>
									<TableCell>{fieldName}</TableCell>
									<TableCell>
										<div className="flex flex-wrap gap-2">
											<Badge variant="outline">{field.type}</Badge>
											{field.mutable && (
												<Badge variant="secondary">Mutable</Badge>
											)}
										</div>
									</TableCell>
								</TableRow>
							))
						)}
					</TableBody>
				</Table>
			</CardContent>
		</Card>
	);
}
