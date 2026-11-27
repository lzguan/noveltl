import { afterEach, describe, expect, it } from "vitest";
import {
	ADMIN_TOKEN_COOKIE,
	clearAdminCookie,
	readAdminToken,
	serializeAdminCookie,
} from "./admin.server";

const originalNodeEnv = process.env.NODE_ENV;

afterEach(() => {
	process.env.NODE_ENV = originalNodeEnv;
});

describe("admin cookie helpers", () => {
	it("reads token from Cookie header", () => {
		expect(readAdminToken(null)).toBeNull();
		expect(readAdminToken("other=1")).toBeNull();
		expect(readAdminToken(`${ADMIN_TOKEN_COOKIE}=abc.def`)).toBe("abc.def");
		expect(readAdminToken(`a=1; ${ADMIN_TOKEN_COOKIE}=tok%2Een; b=2`)).toBe("tok.en");
		expect(readAdminToken(`${ADMIN_TOKEN_COOKIE}=%E0%A4%A`)).toBeNull();
	});

	it("serializes HttpOnly SameSite=Lax Path=/admin cookie without Secure outside production", () => {
		process.env.NODE_ENV = "development";
		const header = serializeAdminCookie("payload.sig", 3600);
		expect(header).toBe(
			`${ADMIN_TOKEN_COOKIE}=payload.sig; HttpOnly; SameSite=Lax; Path=/admin; Max-Age=3600`,
		);
		expect(header).not.toContain("Secure");
	});

	it("adds Secure attribute in production", () => {
		process.env.NODE_ENV = "production";
		const setHeader = serializeAdminCookie("payload.sig", 60);
		expect(setHeader).toContain("; Secure");
		const clearHeader = clearAdminCookie();
		expect(clearHeader).toBe(
			`${ADMIN_TOKEN_COOKIE}=; HttpOnly; SameSite=Lax; Path=/admin; Max-Age=0; Secure`,
		);
	});
});
