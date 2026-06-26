export const customFetch = async <T>(url: string, options: RequestInit): Promise<T> => {
	const token = localStorage.getItem("access_token");

	const res = await fetch(url, {
		...options,
		headers: {
			...options.headers,
			...(token ? { Authorization: `Bearer ${token}` } : {}),
		},
	});

	const body = [204, 205, 304].includes(res.status) ? null : await res.text();
	const data = body ? JSON.parse(body) : {};

	return { status: res.status, data, headers: res.headers } as T;
};
