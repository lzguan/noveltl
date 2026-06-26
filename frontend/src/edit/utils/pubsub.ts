import { Effect } from "effect";
import type { SubscriberFn } from "../controller/types/controllerTypes";

export function buildPubSub<GettersT, TriggerEventT>() {
	const subscribers = new Map<number, Set<SubscriberFn<GettersT, TriggerEventT>>>();

	const subscribe = (
		fn: SubscriberFn<GettersT, TriggerEventT>,
		priority: number = Infinity,
	): (() => void) => {
		if (!subscribers.has(priority)) {
			subscribers.set(priority, new Set());
		}
		subscribers.get(priority)!.add(fn);
		return () => {
			subscribers.get(priority)!.delete(fn);
			if (subscribers.get(priority)!.size === 0) {
				subscribers.delete(priority);
			}
		};
	};

	const raiseTriggerEvent = (getters: GettersT, event: TriggerEventT): Effect.Effect<void> => {
		const effects: Effect.Effect<void>[] = [];
		for (const [, fns] of Array.from(subscribers).sort(([p1], [p2]) => p1 - p2)) {
			for (const fn of fns) {
				effects.push(fn(getters, event));
			}
		}
		return Effect.all(effects);
	};

	return { subscribe, raiseTriggerEvent };
}
