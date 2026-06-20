import { Effect } from "effect";
import type { SubscriberFn } from "../controller/types/controllerTypes";

export function buildPubSub<GettersT, TriggerEventT>() {
	const subscribers = new Set<SubscriberFn<GettersT, TriggerEventT>>();

	const subscribe = (fn: SubscriberFn<GettersT, TriggerEventT>): (() => void) => {
		subscribers.add(fn);
		return () => {
			subscribers.delete(fn);
		};
	};

	const raiseTriggerEvent = (getters: GettersT, event: TriggerEventT): Effect.Effect<void> => {
		const effects = [];
		for (const fn of subscribers) {
			effects.push(fn(getters, event));
		}
		return Effect.all(effects);
	};

	return { subscribe, raiseTriggerEvent };
}
