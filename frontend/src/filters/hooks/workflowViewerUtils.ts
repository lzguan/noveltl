export const WORKFLOW_VIEWER_PAGE_SIZE = 50;

export function requestError(action: string, status: number) {
	return `${action} failed with status ${status}.`;
}

export function errorMessage(error: unknown) {
	return error instanceof Error ? error.message : String(error);
}
