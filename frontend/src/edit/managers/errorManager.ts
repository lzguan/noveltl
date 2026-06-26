import { Effect } from "effect";
import type { NovelGetters, SubscriberFn, TriggerEvent } from "../controller/types/controllerTypes";

type ErrorManagerGetters = Record<string, never>;

type ErrorTriggerEvent = { eventType: "errorOccured"; error: unknown };

/**
 * Centralises error events from the controller. Incoming `errorOccured`
 * triggers are logged to the console and forwarded to internal subscribers
 * (future home for a banner / toast / panel).
 */
export interface ErrorManager {
	/** Plugged directly into {@code ctrl.subscribe()}. */
	handleTriggerEvent: SubscriberFn<NovelGetters, TriggerEvent>;
	/** Subscribe your own error UI here. */
	subscribe: (callback: SubscriberFn<ErrorManagerGetters, ErrorTriggerEvent>) => () => void;
	/** Imperatively log an error (for non-controller sources). */
	logError: (error: unknown) => void;
	getters: ErrorManagerGetters;
}

export function buildErrorManager(): ErrorManager {
	const subscribers = new Set<SubscriberFn<ErrorManagerGetters, ErrorTriggerEvent>>();

	const getters: ErrorManagerGetters = {};

	const logError = (error: unknown) => {
		const message = error instanceof Error ? error.message : String(error);
		console.error("[errorManager]", message);
		console.dir(error);
		for (const sub of subscribers) {
			Effect.runSync(
				sub(getters, { eventType: "errorOccured", error }).pipe(
					Effect.catchAll(() => Effect.succeed(undefined)),
				),
			);
		}
	};

	const handleTriggerEvent: SubscriberFn<NovelGetters, TriggerEvent> = (_getters, event) =>
		Effect.sync(() => {
			if (event.eventType !== "errorOccured") return;
			if (event.from === "dataManager") {
				logError(event.error);
			} else {
				for (const d of event.data) {
					logError(d.error);
				}
			}
		});

	return {
		handleTriggerEvent,
		subscribe: (callback) => {
			subscribers.add(callback);
			return () => void subscribers.delete(callback);
		},
		logError,
		getters,
	};
}
