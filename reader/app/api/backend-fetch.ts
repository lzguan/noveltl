const DEFAULT_BACKEND_URL = "http://reader-api:8001";
const TIMEOUT_MS = 10_000;

export class BackendError extends Error {
	readonly status: number;

	constructor(status: number, message: string) {
		super(message);
		this.name = "BackendError";
		this.status = status;
	}
}

export class BackendUnavailableError extends Error {
	constructor(message: string, options?: ErrorOptions) {
		super(message, options);
		this.name = "BackendUnavailableError";
	}
}

function backendBaseUrl(): string {
	const configured = process.env.READER_BACKEND_URL?.trim();
	return (configured || DEFAULT_BACKEND_URL).replace(/\/+$/, "");
}

export async function backendFetch<T>(path: string, options: RequestInit): Promise<T> {
	const url = `${backendBaseUrl()}${path}`;
	let res: Response;
	try {
		res = await fetch(url, {
			...options,
			headers: { Accept: "application/json", ...options.headers },
			signal: options.signal ?? AbortSignal.timeout(TIMEOUT_MS),
		});
	} catch (error) {
		throw new BackendUnavailableError(`Backend request failed: ${path}`, { cause: error });
	}

	if (!res.ok) {
		await res.body?.cancel();
		if (res.status >= 500) {
			throw new BackendUnavailableError(`Backend returned ${res.status}: ${path}`);
		}
		throw new BackendError(res.status, `Backend returned ${res.status}: ${path}`);
	}

	try {
		return await res.json();
	} catch (error) {
		throw new BackendUnavailableError(`Backend returned invalid JSON: ${path}`, {
			cause: error,
		});
	}
}
