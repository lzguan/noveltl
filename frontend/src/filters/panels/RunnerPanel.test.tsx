import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RunnerPanel } from "./RunnerPanel";

const cases = [
	["Label source", "label-source-form"],
	["Annotation", "annotation-form"],
	["Map", "map-form"],
	["Filter", "filter-form"],
	["Group", "group-form"],
] as const;

vi.mock("../components/runnerForms/AnnotationRunnerForm", () => ({
	AnnotationRunnerForm: ({ enabled }: { enabled: boolean }) => (
		<div data-enabled={enabled} data-testid="annotation-form" />
	),
}));
vi.mock("../components/runnerForms/FilterRunnerForm", () => ({
	FilterRunnerForm: ({ enabled }: { enabled: boolean }) => (
		<div data-enabled={enabled} data-testid="filter-form" />
	),
}));
vi.mock("../components/runnerForms/GroupRunnerForm", () => ({
	GroupRunnerForm: ({ enabled }: { enabled: boolean }) => (
		<div data-enabled={enabled} data-testid="group-form" />
	),
}));
vi.mock("../components/runnerForms/LabelSourceRunnerForm", () => ({
	LabelSourceRunnerForm: ({ enabled }: { enabled: boolean }) => (
		<div data-enabled={enabled} data-testid="label-source-form" />
	),
}));
vi.mock("../components/runnerForms/MapRunnerForm", () => ({
	MapRunnerForm: ({ enabled }: { enabled: boolean }) => (
		<div data-enabled={enabled} data-testid="map-form" />
	),
}));

describe("RunnerPanel", () => {
	it.each(cases)("shows and enables only the %s runner form", (operation, testId) => {
		render(<RunnerPanel novelId="novel-1" enabled />);
		fireEvent.click(screen.getByRole("radio", { name: operation }));

		for (const [, candidateId] of cases) {
			const form = screen.getByTestId(candidateId);
			if (candidateId === testId) {
				expect(form).toBeVisible();
				expect(form).toHaveAttribute("data-enabled", "true");
			} else {
				expect(form).not.toBeVisible();
				expect(form).toHaveAttribute("data-enabled", "false");
			}
		}
	});
});
