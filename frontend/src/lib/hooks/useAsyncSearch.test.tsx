import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ASYNC_SEARCH_DEBOUNCE_MS, useAsyncSearch } from "./useAsyncSearch";

describe("useAsyncSearch", () => {
	afterEach(() => vi.useRealTimers());

	it("debounces keywords and cancels stale searches", async () => {
		vi.useFakeTimers();
		const fetchResults = vi.fn(async (keyword: string, signal: AbortSignal) => {
			if (signal.aborted) return [];
			return [keyword];
		});
		const { result } = renderHook(() => useAsyncSearch(fetchResults, true));

		act(() => result.current.setSearchKeyword("first"));
		await act(() => vi.advanceTimersByTimeAsync(ASYNC_SEARCH_DEBOUNCE_MS - 1));
		expect(fetchResults).not.toHaveBeenCalled();
		act(() => result.current.setSearchKeyword("second"));
		await act(() => vi.advanceTimersByTimeAsync(ASYNC_SEARCH_DEBOUNCE_MS));

		expect(fetchResults).toHaveBeenCalledOnce();
		expect(fetchResults).toHaveBeenCalledWith("second", expect.any(AbortSignal));
		expect(result.current.results).toEqual({ status: "ready", data: ["second"] });
	});

	it("does not search while disabled", async () => {
		vi.useFakeTimers();
		const fetchResults = vi.fn(async () => ["result"]);
		const { result } = renderHook(() => useAsyncSearch(fetchResults, false));

		await act(() => vi.advanceTimersByTimeAsync(ASYNC_SEARCH_DEBOUNCE_MS));

		expect(fetchResults).not.toHaveBeenCalled();
		expect(result.current.results).toEqual({ status: "idle" });
	});
});
