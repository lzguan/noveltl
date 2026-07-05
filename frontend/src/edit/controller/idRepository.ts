import { createLogger } from "@/lib/logging";
import {
	type IDRepository,
	type IdStatus,
	type Kind,
	type IdentifiableKind,
	type ExistableKind,
	ProvId,
	ServEx,
	ServId,
	type InFlightIdStatus,
	isInFlight,
	exitStatus,
	ActionHappened,
	type GroundIdStatus,
	entryStatus,
	ProvTypes,
	LProvId,
	CServId,
	CCServId,
	LGServId,
	LDServId,
	LServEx,
	AServId,
	ALRServId,
	ServTypes,
	isTerminal,
	identifiableKinds,
	type ProvServKind,
	type AnyProvServKind,
	kinds,
	existableKinds,
} from "./types/idTypes";
import {
	ResourceConflictException,
	NotFoundException,
	NotReserveableException,
} from "./types/errors";
import { Effect } from "effect";
import type { AnyReservation } from "./types/requestTypes";
import { forEachKind } from "./types/helperTypes";

const logger = createLogger("IdRepository");

type ServIdStatus<K extends IdentifiableKind> = {
	serverId: ServTypes[K] | null;
	status: IdStatus;
	lockCount: number;
};
type ServExistsStatus<K extends ExistableKind> = {
	serverExists: ServTypes[K] | null;
	status: IdStatus;
	lockCount: number;
};

// Convenience types
type IdentifiableKindMap = {
	[K in IdentifiableKind]: Map<ProvTypes[K], ServIdStatus<K>>;
};
type RevMap = {
	[K in IdentifiableKind]: Map<ServTypes[K], ProvTypes[K]>;
};

type ExistableKindMap = {
	[K in ExistableKind]: Map<ProvTypes[K], ServExistsStatus<K>>;
};

export function buildIdRepository(): IDRepository {
	let counterRef = 0;
	const identifiableKindMap: IdentifiableKindMap = {
		labelGroup: new Map<ProvTypes["labelGroup"], ServIdStatus<"labelGroup">>(),
		labelData: new Map<ProvTypes["labelData"], ServIdStatus<"labelData">>(),
		chapterContent: new Map<ProvTypes["chapterContent"], ServIdStatus<"chapterContent">>(),
		chapter: new Map<ProvTypes["chapter"], ServIdStatus<"chapter">>(),
		autoLabel: new Map<ProvTypes["autoLabel"], ServIdStatus<"autoLabel">>(),
		autoLabelRun: new Map<ProvTypes["autoLabelRun"], ServIdStatus<"autoLabelRun">>(),
	};

	const existableKindMap: ExistableKindMap = {
		label: new Map<ProvTypes["label"], ServExistsStatus<"label">>(),
	};

	const revMap: RevMap = {
		labelGroup: new Map<ServTypes["labelGroup"], ProvTypes["labelGroup"]>(),
		labelData: new Map<ServTypes["labelData"], ProvTypes["labelData"]>(),
		chapterContent: new Map<ServTypes["chapterContent"], ProvTypes["chapterContent"]>(),
		chapter: new Map<ServTypes["chapter"], ProvTypes["chapter"]>(),
		autoLabel: new Map<ServTypes["autoLabel"], ProvTypes["autoLabel"]>(),
		autoLabelRun: new Map<ServTypes["autoLabelRun"], ProvTypes["autoLabelRun"]>(),
	};

	function newId(kind: "chapter"): ProvTypes["chapter"];
	function newId(kind: "chapterContent"): ProvTypes["chapterContent"];
	function newId(kind: "labelGroup"): ProvTypes["labelGroup"];
	function newId(kind: "labelData"): ProvTypes["labelData"];
	function newId(kind: "label"): ProvTypes["label"];
	function newId(kind: "autoLabel"): ProvTypes["autoLabel"];
	function newId(kind: "autoLabelRun"): ProvTypes["autoLabelRun"];

	function newId(kind: Kind): ProvTypes[Kind] {
		const provId = ProvId(`provisional-${counterRef++}`);
		const id = ProvTypes[kind](provId);
		// @ts-expect-error
		if (identifiableKinds.includes(kind)) {
			// @ts-expect-error
			identifiableKindMap[kind as keyof IdentifiableKindMap].set(id, {
				serverId: null,
				status: "pending",
				lockCount: 0,
			});
		} else {
			// @ts-expect-error
			existableKindMap[kind as keyof ExistableKindMap].set(id, {
				serverExists: null,
				status: "pending",
				lockCount: 0,
			});
		}
		return id;
	}

	function newIdAndBindId(
		params: Omit<ProvServKind<"chapter">, "provId">,
	): Effect.Effect<ProvTypes["chapter"], ResourceConflictException>;
	function newIdAndBindId(
		params: Omit<ProvServKind<"chapterContent">, "provId">,
	): Effect.Effect<ProvTypes["chapterContent"], ResourceConflictException>;
	function newIdAndBindId(
		params: Omit<ProvServKind<"labelGroup">, "provId">,
	): Effect.Effect<ProvTypes["labelGroup"], ResourceConflictException>;
	function newIdAndBindId(
		params: Omit<ProvServKind<"labelData">, "provId">,
	): Effect.Effect<ProvTypes["labelData"], ResourceConflictException>;
	function newIdAndBindId(
		params: Omit<ProvServKind<"autoLabel">, "provId">,
	): Effect.Effect<ProvTypes["autoLabel"], ResourceConflictException>;
	function newIdAndBindId(
		params: Omit<ProvServKind<"autoLabelRun">, "provId">,
	): Effect.Effect<ProvTypes["autoLabelRun"], ResourceConflictException>;

	function newIdAndBindId({
		kind,
		servId,
	}: {
		kind: IdentifiableKind;
		servId: ServId;
	}): Effect.Effect<ProvTypes[IdentifiableKind], ResourceConflictException> {
		const provId = ProvId(`provisional-${counterRef++}`);
		const id = ProvTypes[kind](provId);
		// @ts-expect-error
		const existing = revMap[kind].get(servId);
		if (existing) {
			// @ts-expect-error
			const entry = identifiableKindMap[kind].get(existing);
			if (entry && (entry.status === "clean" || entry.status === "locked")) {
				return Effect.succeed(existing);
			}
			return Effect.fail(new ResourceConflictException({ id: servId }));
		}
		// @ts-expect-error
		identifiableKindMap[kind].set(id, {
			serverId: servId,
			status: "clean",
			lockCount: 0,
		});
		// @ts-expect-error
		revMap[kind].set(servId, id);
		return Effect.succeed(id);
	}

	function newIdAndBindExists(
		params: Omit<ProvServKind<"label">, "provId" | "servId">,
	): Effect.Effect<ProvTypes["label"]>;

	function newIdAndBindExists({ kind }: { kind: "label" }): Effect.Effect<ProvTypes["label"]> {
		const id = ProvTypes[kind](ProvId(`provisional-${counterRef++}`));
		existableKindMap[kind].set(id, {
			serverExists: ServTypes[kind](ServEx(true)),
			status: "clean",
			lockCount: 0,
		});
		return Effect.succeed(id);
	}

	function getServerId(
		params: Omit<ProvServKind<"chapter">, "servId">,
	): Effect.Effect<CServId | null, NotFoundException>;
	function getServerId(
		params: Omit<ProvServKind<"chapterContent">, "servId">,
	): Effect.Effect<CCServId | null, NotFoundException>;
	function getServerId(
		params: Omit<ProvServKind<"labelGroup">, "servId">,
	): Effect.Effect<LGServId | null, NotFoundException>;
	function getServerId(
		params: Omit<ProvServKind<"labelData">, "servId">,
	): Effect.Effect<LDServId | null, NotFoundException>;
	function getServerId(
		params: Omit<ProvServKind<"autoLabel">, "servId">,
	): Effect.Effect<AServId | null, NotFoundException>;
	function getServerId(
		params: Omit<ProvServKind<"autoLabelRun">, "servId">,
	): Effect.Effect<ALRServId | null, NotFoundException>;

	function getServerId<K extends IdentifiableKind>({
		kind,
		provId,
	}: {
		kind: K;
		provId: ProvTypes[K];
	}): Effect.Effect<ServId | null, NotFoundException> {
		const entry = identifiableKindMap[kind].get(provId);
		if (!entry) {
			return Effect.fail(new NotFoundException());
		}
		return Effect.succeed(entry.serverId);
	}

	function getServerExists(
		params: ProvServKind<"label">,
	): Effect.Effect<LServEx | null, NotFoundException>;

	function getServerExists<K extends ExistableKind>({
		kind,
		provId,
	}: {
		kind: K;
		provId: ProvTypes[K];
	}): Effect.Effect<ServEx | null, NotFoundException> {
		const entry = existableKindMap[kind].get(provId);
		if (!entry) {
			return Effect.fail(new NotFoundException());
		}
		return Effect.succeed(entry.serverExists);
	}

	function bindServerId(
		params: AnyProvServKind<IdentifiableKind>,
	): Effect.Effect<void, NotFoundException | ResourceConflictException>;

	function bindServerId({ kind, provId, servId }: AnyProvServKind<IdentifiableKind>) {
		// @ts-expect-error
		const entry = identifiableKindMap[kind].get(provId);
		// @ts-expect-error
		if (revMap[kind].has(servId)) {
			return Effect.fail(new ResourceConflictException({ id: servId }));
		}
		if (!entry) {
			logger.error(`Provisional id ${provId} not found for kind ${kind} in bindServerId`);
			return Effect.fail(new NotFoundException());
		}
		if (entry.serverId !== null) {
			return Effect.fail(new ResourceConflictException({ id: servId }));
		}
		// @ts-expect-error
		revMap[kind].set(servId, provId);
		entry.serverId = servId;
		return Effect.succeed(void 0);
	}

	function bindServerExists(
		params: AnyProvServKind<ExistableKind>,
	): Effect.Effect<void, NotFoundException>;

	function bindServerExists<K extends ExistableKind>({
		kind,
		provId,
	}: {
		kind: K;
		provId: ProvTypes[K];
	}) {
		const entry = existableKindMap[kind].get(provId);
		if (!entry) {
			logger.error(`Provisional id ${provId} not found for kind ${kind} in bindServerExists`);
			return Effect.fail(new NotFoundException());
		}
		entry.serverExists = LServEx(true);
		return Effect.succeed(void 0);
	}

	function idObjState(
		params: Omit<AnyReservation<Kind>, "desiredState">,
	): Effect.Effect<IdStatus, NotFoundException>;

	function idObjState({
		kind,
		id,
	}: {
		kind: Kind;
		id: ProvTypes[Kind];
	}): Effect.Effect<IdStatus, NotFoundException> {
		// @ts-expect-error
		if (identifiableKinds.includes(kind)) {
			// @ts-expect-error
			const entry = identifiableKindMap[kind].get(id);
			if (!entry) {
				logger.error(`Provisional id ${id} not found for kind ${kind} in idObjState`);
				return Effect.fail(new NotFoundException());
			}
			return Effect.succeed(entry.status);
		} else {
			// @ts-expect-error
			const entry = existableKindMap[kind].get(id);
			if (!entry) {
				logger.error(`Provisional id ${id} not found for kind ${kind} in idObjState`);
				return Effect.fail(new NotFoundException());
			}
			return Effect.succeed(entry.status);
		}
	}
	function isReserveable(params: AnyReservation<Kind>): Effect.Effect<boolean, NotFoundException>;
	function isReserveable({
		kind,
		id,
		desiredState,
	}: AnyReservation<Kind>): Effect.Effect<boolean, NotFoundException> {
		return Effect.gen(function* () {
			let currentState: IdStatus;
			let serverState: ServId | ServEx | null;
			// @ts-expect-error
			if (identifiableKinds.includes(kind)) {
				currentState = yield* idObjState({ kind, id });
				// @ts-expect-error
				serverState = identifiableKindMap[kind].get(id)?.serverId ?? null;
			} else {
				currentState = yield* idObjState({ kind: "label", id: id as LProvId });
				// @ts-expect-error
				serverState = existableKindMap[kind].get(id as LProvId)?.serverExists ?? null;
			}
			if (desiredState === "creating") {
				return currentState === "pending" && serverState === null;
			} else if (desiredState === "updating" || desiredState === "idUpdating") {
				return currentState === "clean" && serverState !== null;
			} else if (desiredState === "locked") {
				return (
					(currentState === "clean" || currentState === "locked") && serverState !== null
				);
			} else if (desiredState === "deleting") {
				return currentState === "clean" && serverState !== null;
			} else if (desiredState === "detaching") {
				return currentState === "clean" && serverState !== null;
			} else if (desiredState === "loading") {
				return currentState === "pending";
			} else if (desiredState === "killing") {
				return currentState === "pending";
			} else {
				return false;
			}
		});
	}

	function reserveIdObjState(
		params: AnyReservation<Kind>,
	): Effect.Effect<void, NotFoundException | NotReserveableException>;

	function reserveIdObjState(reservation: AnyReservation<Kind>) {
		return Effect.gen(function* () {
			const { kind, id, desiredState } = reservation;
			const reserveable = yield* isReserveable(reservation);
			if (!reserveable) {
				return yield* Effect.fail(new NotReserveableException());
			}
			let entry:
				| {
						status: IdStatus;
						lockCount: number;
				  }
				| undefined;
			// @ts-expect-error
			if (identifiableKinds.includes(kind)) {
				// @ts-expect-error
				entry = identifiableKindMap[kind].get(id);
			} else {
				// @ts-expect-error
				entry = existableKindMap[kind].get(id);
			}
			if (!entry) {
				return yield* Effect.fail(new NotFoundException());
			}
			entry.status = desiredState;
			if (desiredState === "locked") {
				entry.lockCount += 1;
			}
			return;
		});
	}

	function releaseIdObjState(post: (status: InFlightIdStatus) => GroundIdStatus) {
		return ({ kind, id }: Omit<AnyReservation<Kind>, "desiredState">) => {
			let entry: ServExistsStatus<ExistableKind> | ServIdStatus<IdentifiableKind> | undefined;
			// @ts-expect-error
			if (identifiableKinds.includes(kind)) {
				// @ts-expect-error
				entry = identifiableKindMap[kind].get(id);
			} else {
				// @ts-expect-error
				entry = existableKindMap[kind].get(id);
			}
			if (!entry) {
				return Effect.fail(new NotFoundException());
			}
			if (!isInFlight(entry.status)) {
				return Effect.succeed(ActionHappened(false));
			}
			if (entry.status === "locked") {
				entry.lockCount = Math.max(0, entry.lockCount - 1);
				if (entry.lockCount >= 1) {
					return Effect.succeed(ActionHappened(true));
				}
			}
			entry.status = post(entry.status);
			if (
				// @ts-expect-error
				identifiableKinds.includes(kind) &&
				isTerminal(entry.status) &&
				"serverId" in entry
			) {
				// @ts-expect-error
				revMap[kind].delete(entry.serverId as ServTypes[IdentifiableKind]);
				// @ts-expect-error
				identifiableKindMap[kind].delete(id as ProvTypes[IdentifiableKind]);
			}
			return Effect.succeed(ActionHappened(true));
		};
	}

	function releaseIdObjStateOnSuccess(
		params: Omit<AnyReservation<Kind>, "desiredState">,
	): Effect.Effect<ActionHappened, NotFoundException>;

	function releaseIdObjStateOnSuccess(params: Omit<AnyReservation<Kind>, "desiredState">) {
		return releaseIdObjState(exitStatus)(params);
	}
	const releaseIdObjStateOnFailure = releaseIdObjState(entryStatus);

	const gc = () => {
		const keys: Record<Kind, [ProvId, Kind][]> = kinds.reduce(
			(acc, kind) => {
				acc[kind] = [];
				return acc;
			},
			{} as Record<Kind, [ProvId, Kind][]>,
		);
		for (const kind of identifiableKinds) {
			for (const [provId, entry] of identifiableKindMap[kind]) {
				if (isTerminal(entry.status)) {
					keys[kind].push([provId, kind]);
				}
			}
		}
		for (const kind of existableKinds) {
			for (const [provId, entry] of existableKindMap[kind]) {
				if (isTerminal(entry.status)) {
					keys[kind].push([provId, kind]);
				}
			}
		}
		Effect.runSync(
			forEachKind(
				keys,
				([provId, kind]: [ProvId, Kind]) =>
					Effect.sync(() => {
						// @ts-expect-error
						if (identifiableKinds.includes(kind)) {
							// @ts-expect-error
							identifiableKindMap[kind].delete(provId);
						} else {
							// @ts-expect-error
							existableKindMap[kind].delete(provId);
						}
					}),
				kinds,
			),
		);
	};

	function queryProvId(
		params: Omit<ProvServKind<"labelGroup">, "provId">,
	): Effect.Effect<ProvTypes["labelGroup"] | null>;
	function queryProvId(
		params: Omit<ProvServKind<"labelData">, "provId">,
	): Effect.Effect<ProvTypes["labelData"] | null>;
	function queryProvId(
		params: Omit<ProvServKind<"chapterContent">, "provId">,
	): Effect.Effect<ProvTypes["chapterContent"] | null>;
	function queryProvId(
		params: Omit<ProvServKind<"chapter">, "provId">,
	): Effect.Effect<ProvTypes["chapter"] | null>;
	function queryProvId(
		params: Omit<ProvServKind<"autoLabel">, "provId">,
	): Effect.Effect<ProvTypes["autoLabel"] | null>;
	function queryProvId(
		params: Omit<ProvServKind<"autoLabelRun">, "provId">,
	): Effect.Effect<ProvTypes["autoLabelRun"] | null>;

	function queryProvId({
		kind,
		servId,
	}: {
		kind: IdentifiableKind;
		servId: ServTypes[IdentifiableKind];
	}): Effect.Effect<ProvTypes[IdentifiableKind] | null> {
		// @ts-expect-error
		return Effect.succeed(revMap[kind].get(servId) ?? null);
	}

	return {
		newId,
		newIdAndBindId,
		newIdAndBindExists,
		getServerId,
		getServerExists,
		bindServerId,
		bindServerExists,
		idObjState,
		isReserveable,
		reserveIdObjState,
		releaseIdObjStateOnSuccess,
		releaseIdObjStateOnFailure,
		queryProvId,
		gc,
	};
}
