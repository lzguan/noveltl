import { data, Form, Link, redirect } from "react-router";
import {
	AdminApiError,
	clearAdminCookie,
	createAdminPartner,
	deleteAdminNovel,
	listAdminNovels,
	listAdminPartners,
	mintAdminPartnerKey,
	readAdminToken,
	revokeAdminKey,
} from "../lib/admin.server";
import type { Route } from "./+types/admin.dashboard";

const NO_STORE_HEADERS = { "Cache-Control": "no-store" };

type AdminActionResult = {
	error?: string;
	notice?: string;
	mintedKey?: {
		partnerName: string;
		keyPrefix: string;
		apiKey: string;
	};
};

function redirectToLogin(clearCookie: boolean) {
	const headers: Record<string, string> = { ...NO_STORE_HEADERS };
	if (clearCookie) {
		headers["Set-Cookie"] = clearAdminCookie();
	}
	return redirect("/admin/login", { headers });
}

function formatDate(iso: string): string {
	const parsed = new Date(iso);
	if (Number.isNaN(parsed.getTime())) return iso;
	return parsed.toISOString().slice(0, 10);
}

export async function loader({ request }: Route.LoaderArgs) {
	const token = readAdminToken(request.headers.get("Cookie"));
	if (!token) {
		throw redirectToLogin(false);
	}

	try {
		const [partners, novels] = await Promise.all([
			listAdminPartners(token),
			listAdminNovels(token),
		]);
		return data({ partners, novels }, { headers: NO_STORE_HEADERS });
	} catch (error) {
		if (error instanceof AdminApiError && (error.status === 401 || error.status === 503)) {
			throw redirectToLogin(true);
		}
		throw error;
	}
}

export async function action({ request }: Route.ActionArgs) {
	const formData = await request.formData();
	const intent = formData.get("intent");

	if (intent === "logout") {
		return redirectToLogin(true);
	}

	const token = readAdminToken(request.headers.get("Cookie"));
	if (!token) {
		return redirectToLogin(false);
	}

	try {
		if (intent === "create-partner") {
			const rawName = formData.get("name");
			const name = typeof rawName === "string" ? rawName.trim() : "";
			if (!name) {
				return data<AdminActionResult>(
					{ error: "Partner name is required." },
					{ status: 400, headers: NO_STORE_HEADERS },
				);
			}
			const created = await createAdminPartner(token, name);
			return data<AdminActionResult>(
				{ notice: `Created partner "${created.name}".` },
				{ headers: NO_STORE_HEADERS },
			);
		}

		if (intent === "mint-key") {
			const partnerId = formData.get("partnerId");
			const partnerName = formData.get("partnerName");
			if (typeof partnerId !== "string" || !partnerId) {
				return data<AdminActionResult>(
					{ error: "Missing partner ID." },
					{ status: 400, headers: NO_STORE_HEADERS },
				);
			}
			const minted = await mintAdminPartnerKey(token, partnerId);
			return data<AdminActionResult>(
				{
					mintedKey: {
						partnerName:
							typeof partnerName === "string" && partnerName
								? partnerName
								: partnerId,
						keyPrefix: minted.keyPrefix,
						apiKey: minted.apiKey,
					},
				},
				{ headers: NO_STORE_HEADERS },
			);
		}

		if (intent === "revoke-key") {
			const keyId = formData.get("keyId");
			if (typeof keyId !== "string" || !keyId) {
				return data<AdminActionResult>(
					{ error: "Missing key ID." },
					{ status: 400, headers: NO_STORE_HEADERS },
				);
			}
			await revokeAdminKey(token, keyId);
			return data<AdminActionResult>(
				{ notice: "API key revoked." },
				{ headers: NO_STORE_HEADERS },
			);
		}

		if (intent === "delete-novel") {
			const novelId = formData.get("novelId");
			if (typeof novelId !== "string" || !novelId) {
				return data<AdminActionResult>(
					{ error: "Missing novel ID." },
					{ status: 400, headers: NO_STORE_HEADERS },
				);
			}
			await deleteAdminNovel(token, novelId);
			return data<AdminActionResult>(
				{ notice: "Novel deleted." },
				{ headers: NO_STORE_HEADERS },
			);
		}

		return data<AdminActionResult>(
			{ error: "Unsupported action." },
			{ status: 400, headers: NO_STORE_HEADERS },
		);
	} catch (error) {
		if (error instanceof AdminApiError) {
			if (error.status === 401 || error.status === 503) {
				return redirectToLogin(true);
			}
			return data<AdminActionResult>(
				{ error: error.detail },
				{ status: error.status >= 400 ? error.status : 502, headers: NO_STORE_HEADERS },
			);
		}
		return data<AdminActionResult>(
			{ error: "Request failed. Please try again." },
			{ status: 502, headers: NO_STORE_HEADERS },
		);
	}
}

export function headers() {
	return NO_STORE_HEADERS;
}

export function meta() {
	return [{ title: "Admin · Reader" }];
}

export default function AdminDashboard({ loaderData, actionData }: Route.ComponentProps) {
	const { partners, novels } = loaderData;

	return (
		<>
			<header className="border-b border-line">
				<div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-3">
					<div className="flex items-center gap-4">
						<span className="font-semibold text-ink">Reader Admin</span>
						<Link to="/" className="text-sm">
							Public library
						</Link>
					</div>
					<Form method="post">
						<input type="hidden" name="intent" value="logout" />
						<button
							type="submit"
							className="cursor-pointer rounded border border-line px-3 py-1 text-sm hover:bg-hover"
						>
							Sign out
						</button>
					</Form>
				</div>
			</header>

			<main className="mx-auto max-w-4xl space-y-8 px-4 py-6">
				{actionData?.mintedKey ? (
					<section
						role="status"
						className="rounded border border-amber-500/50 bg-amber-500/10 p-4"
					>
						<h2 className="text-sm font-semibold">
							New API key for {actionData.mintedKey.partnerName}
						</h2>
						<p className="mt-1 text-sm text-muted">
							Copy this key now; it won&apos;t be shown again.
						</p>
						<code className="mt-2 block overflow-x-auto rounded border border-line bg-page px-3 py-2 font-mono text-sm select-all">
							{actionData.mintedKey.apiKey}
						</code>
					</section>
				) : null}

				{actionData?.notice ? (
					<p
						role="status"
						className="rounded border border-line bg-hover px-3 py-2 text-sm"
					>
						{actionData.notice}
					</p>
				) : null}

				{actionData?.error ? (
					<p
						role="alert"
						className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300"
					>
						{actionData.error}
					</p>
				) : null}

				<section aria-labelledby="partners-heading" className="space-y-4">
					<div className="flex flex-wrap items-center justify-between gap-3">
						<h1 id="partners-heading" className="text-lg font-semibold">
							Partners &amp; API Keys
						</h1>
						<Form method="post" className="flex flex-wrap items-center gap-2">
							<input type="hidden" name="intent" value="create-partner" />
							<label htmlFor="new-partner-name" className="sr-only">
								Partner name
							</label>
							<input
								id="new-partner-name"
								name="name"
								type="text"
								required
								placeholder="New partner name"
								className="rounded border border-line bg-page px-3 py-1.5 text-sm text-ink"
							/>
							<button
								type="submit"
								className="cursor-pointer rounded border border-line px-3 py-1.5 text-sm font-medium hover:bg-hover"
							>
								Create partner
							</button>
						</Form>
					</div>

					{partners.length === 0 ? (
						<p className="text-sm text-muted">No partners yet.</p>
					) : (
						<div className="space-y-4">
							{partners.map((partner) => (
								<div
									key={partner.partnerId}
									className="rounded border border-line p-4"
								>
									<div className="flex flex-wrap items-center justify-between gap-2">
										<div>
											<h2 className="font-medium">{partner.name}</h2>
											<p className="text-xs text-muted">
												{partner.novelCount}{" "}
												{partner.novelCount === 1 ? "novel" : "novels"} ·
												Created {formatDate(partner.createdAt)}
											</p>
										</div>
										<Form method="post">
											<input type="hidden" name="intent" value="mint-key" />
											<input
												type="hidden"
												name="partnerId"
												value={partner.partnerId}
											/>
											<input
												type="hidden"
												name="partnerName"
												value={partner.name}
											/>
											<button
												type="submit"
												className="cursor-pointer rounded border border-line px-3 py-1 text-sm hover:bg-hover"
											>
												Mint Key
											</button>
										</Form>
									</div>

									{partner.keys.length === 0 ? (
										<p className="mt-3 text-xs text-muted">
											No keys minted for this partner.
										</p>
									) : (
										<ul className="mt-3 divide-y divide-line border-t border-line">
											{partner.keys.map((key) => {
												const isRevoked = key.revokedAt !== null;
												return (
													<li
														key={key.keyId}
														className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
													>
														<div className="flex flex-wrap items-center gap-3">
															<code className="font-mono text-xs">
																{key.keyPrefix}…
															</code>
															<span
																className={
																	isRevoked
																		? "text-xs text-muted"
																		: "text-xs font-medium"
																}
															>
																{isRevoked
																	? `Revoked (${formatDate(key.revokedAt ?? "")})`
																	: "Active"}
															</span>
															<span className="text-xs text-muted">
																Minted {formatDate(key.createdAt)}
															</span>
														</div>
														{!isRevoked ? (
															<Form method="post">
																<input
																	type="hidden"
																	name="intent"
																	value="revoke-key"
																/>
																<input
																	type="hidden"
																	name="keyId"
																	value={key.keyId}
																/>
																<button
																	type="submit"
																	className="cursor-pointer rounded border border-line px-2.5 py-0.5 text-xs hover:bg-hover"
																>
																	Revoke
																</button>
															</Form>
														) : null}
													</li>
												);
											})}
										</ul>
									)}
								</div>
							))}
						</div>
					)}
				</section>

				<section aria-labelledby="novels-heading" className="space-y-3">
					<h2 id="novels-heading" className="text-lg font-semibold">
						Published Novels{" "}
						<span className="text-sm font-normal text-muted">({novels.length})</span>
					</h2>

					{novels.length === 0 ? (
						<p className="text-sm text-muted">No published novels yet.</p>
					) : (
						<ul className="divide-y divide-line border-y border-line">
							{novels.map((novel) => (
								<li
									key={novel.novelId}
									className="flex flex-wrap items-center justify-between gap-3 py-3"
								>
									<div>
										<Link
											to={`/novel/${novel.novelId}`}
											className="font-medium"
										>
											{novel.title}
										</Link>
										<p className="mt-0.5 text-xs text-muted">
											{novel.partnerName ?? "Unassigned partner"} ·{" "}
											{novel.chapterCount}{" "}
											{novel.chapterCount === 1 ? "chapter" : "chapters"} ·{" "}
											{novel.languageCode} · Updated{" "}
											{formatDate(novel.updatedAt)}
										</p>
									</div>
									<Form method="post">
										<input type="hidden" name="intent" value="delete-novel" />
										<input type="hidden" name="novelId" value={novel.novelId} />
										<button
											type="submit"
											className="cursor-pointer rounded border border-line px-3 py-1 text-xs hover:bg-hover"
										>
											Delete
										</button>
									</Form>
								</li>
							))}
						</ul>
					)}
				</section>
			</main>
		</>
	);
}
