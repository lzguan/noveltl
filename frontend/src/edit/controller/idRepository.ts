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
	CProvId,
	CCProvId,
	LGProvId,
	LDProvId,
	LProvId,
} from "./types/idTypes";
import { NotFoundException, NotReserveableException } from "./types/errors";
import { Effect } from "effect";

// TODO: figure out how to remove boilerplate

const logger = createLogger("IdRepository");

// Convenience types
type IdentifiableKindMap = {
	[K in IdentifiableKind]: Map<
		ProvTypes[K],
		{ serverId: ServId | null; status: IdStatus; lockCount: number }
	>;
};
type ExistableKindMap = {
	[K in ExistableKind]: Map<
		ProvTypes[K],
		{ serverExists: ServEx | null; status: IdStatus; lockCount: number }
	>;
};

type ServIdStatus = { serverId: ServId | null; status: IdStatus; lockCount: number };
type ServExistsStatus = { serverExists: ServEx | null; status: IdStatus; lockCount: number };

export function buildIdRepository(): IDRepository {
	let counterRef = 0;
	const identifiableKindMap: IdentifiableKindMap = {
		labelGroup: new Map<ProvTypes["labelGroup"], ServIdStatus>(),
		labelData: new Map<ProvTypes["labelData"], ServIdStatus>(),
		chapterContent: new Map<ProvTypes["chapterContent"], ServIdStatus>(),
		chapter: new Map<ProvTypes["chapter"], ServIdStatus>(),
	};

	const existableKindMap: ExistableKindMap = {
		label: new Map<ProvTypes["label"], ServExistsStatus>(),
	};

	function newId(kind: "chapter"): ProvTypes["chapter"];
	function newId(kind: "chapterContent"): ProvTypes["chapterContent"];
	function newId(kind: "labelGroup"): ProvTypes["labelGroup"];
	function newId(kind: "labelData"): ProvTypes["labelData"];
	function newId(kind: "label"): ProvTypes["label"];

	function newId(kind: Kind): ProvTypes[Kind] {
		const provId = ProvId(`provisional-${counterRef++}`);
		switch (kind) {
			case "chapter":
				const id = ProvTypes["chapter"](provId);
				identifiableKindMap[kind].set(id, {
					serverId: null,
					status: "pending",
					lockCount: 0,
				});
				return id;
			case "chapterContent":
				const id2 = ProvTypes["chapterContent"](provId);
				identifiableKindMap[kind].set(id2, {
					serverId: null,
					status: "pending",
					lockCount: 0,
				});
				return id2;
			case "labelGroup":
				const id3 = ProvTypes["labelGroup"](provId);
				identifiableKindMap[kind].set(id3, {
					serverId: null,
					status: "pending",
					lockCount: 0,
				});
				return id3;
			case "labelData":
				const id4 = ProvTypes["labelData"](provId);
				identifiableKindMap[kind].set(id4, {
					serverId: null,
					status: "pending",
					lockCount: 0,
				});
				return id4;
			case "label":
				const id5 = ProvTypes["label"](provId);
				existableKindMap[kind].set(id5, {
					serverExists: null,
					status: "pending",
					lockCount: 0,
				});
				return id5;
		}
	}

	function newIdAndBindId(kind: "chapter", serverId: ServId): ProvTypes["chapter"];
	function newIdAndBindId(kind: "chapterContent", serverId: ServId): ProvTypes["chapterContent"];
	function newIdAndBindId(kind: "labelGroup", serverId: ServId): ProvTypes["labelGroup"];
	function newIdAndBindId(kind: "labelData", serverId: ServId): ProvTypes["labelData"];

	function newIdAndBindId(kind: IdentifiableKind, serverId: ServId): ProvId {
		const provId = ProvId(`provisional-${counterRef++}`);
		switch (kind) {
			case "chapter":
				const id = ProvTypes["chapter"](provId);
				identifiableKindMap[kind].set(id, {
					serverId,
					status: "clean",
					lockCount: 0,
				});
				return id;
			case "chapterContent":
				const id2 = ProvTypes["chapterContent"](provId);
				identifiableKindMap[kind].set(id2, {
					serverId,
					status: "clean",
					lockCount: 0,
				});
				return id2;
			case "labelGroup":
				const id3 = ProvTypes["labelGroup"](provId);
				identifiableKindMap[kind].set(id3, {
					serverId,
					status: "clean",
					lockCount: 0,
				});
				return id3;
			case "labelData":
				const id4 = ProvTypes["labelData"](provId);
				identifiableKindMap[kind].set(id4, {
					serverId,
					status: "clean",
					lockCount: 0,
				});
				return id4;
		}
	}

	function newIdAndBindExists(kind: "label"): ProvTypes["label"] {
		const id = ProvTypes["label"](ProvId(`provisional-${counterRef++}`));
		existableKindMap[kind].set(id, {
			serverExists: ServEx(true),
			status: "clean",
			lockCount: 0,
		});
		return id;
	}

	const getServerId = <K extends IdentifiableKind>(kind: K, provisionalId: ProvTypes[K]) => {
		const entry = identifiableKindMap[kind].get(provisionalId);
		if (!entry) {
			return Effect.fail(new NotFoundException());
		}
		return Effect.succeed(entry.serverId);
	};

	const getServerExists = <K extends ExistableKind>(kind: K, provisionalId: ProvTypes[K]) => {
		const entry = existableKindMap[kind].get(provisionalId);
		if (!entry) {
			return Effect.fail(new NotFoundException());
		}
		return Effect.succeed(entry.serverExists);
	};

	const bindServerId = <K extends IdentifiableKind>(
		kind: K,
		provisionalId: ProvTypes[K],
		serverId: ServId,
	) => {
		const entry = identifiableKindMap[kind].get(provisionalId);
		if (!entry) {
			logger.error(
				`Provisional id ${provisionalId} not found for kind ${kind} in bindServerId`,
			);
			return Effect.fail(new NotFoundException());
		}
		return Effect.sync(() => (entry.serverId = serverId));
	};

	const bindServerExists = <K extends ExistableKind>(kind: K, provisionalId: ProvTypes[K]) => {
		const entry = existableKindMap[kind].get(provisionalId);
		if (!entry) {
			logger.error(
				`Provisional id ${provisionalId} not found for kind ${kind} in bindServerExists`,
			);
			return Effect.fail(new NotFoundException());
		}
		return Effect.sync(() => (entry.serverExists = ServEx(true)));
	};

	function idObjState(
		kind: Kind,
		id: ProvTypes[Kind],
	): Effect.Effect<IdStatus, NotFoundException> {
		switch (kind) {
			case "chapter":
				const entry = identifiableKindMap["chapter"].get(id as CProvId);
				if (!entry) {
					logger.error(`Provisional id ${id} not found for kind ${kind} in idObjState`);
					return Effect.fail(new NotFoundException());
				}
				return Effect.succeed(entry.status);
			case "chapterContent":
				const entry2 = identifiableKindMap["chapterContent"].get(id as CCProvId);
				if (!entry2) {
					logger.error(`Provisional id ${id} not found for kind ${kind} in idObjState`);
					return Effect.fail(new NotFoundException());
				}
				return Effect.succeed(entry2.status);
			case "labelGroup":
				const entry3 = identifiableKindMap["labelGroup"].get(id as LGProvId);
				if (!entry3) {
					logger.error(`Provisional id ${id} not found for kind ${kind} in idObjState`);
					return Effect.fail(new NotFoundException());
				}
				return Effect.succeed(entry3.status);
			case "labelData":
				const entry4 = identifiableKindMap["labelData"].get(id as LDProvId);
				if (!entry4) {
					logger.error(`Provisional id ${id} not found for kind ${kind} in idObjState`);
					return Effect.fail(new NotFoundException());
				}
				return Effect.succeed(entry4.status);
			case "label":
				const entry5 = existableKindMap["label"].get(id as LProvId);
				if (!entry5) {
					logger.error(`Provisional id ${id} not found for kind ${kind} in idObjState`);
					return Effect.fail(new NotFoundException());
				}
				return Effect.succeed(entry5.status);
		}
	}

	const isReserveable = (kind: Kind, id: ProvTypes[Kind], desiredState: InFlightIdStatus) =>
		Effect.gen(function* () {
			let currentState: IdStatus;
			let serverState: ServId | ServEx | null;

			switch (kind) {
				case "chapter":
					currentState = yield* idObjState("chapter", id as CProvId);
					serverState =
						identifiableKindMap["chapter"].get(id as CProvId)?.serverId ?? null;
					break;
				case "chapterContent":
					currentState = yield* idObjState("chapterContent", id as CCProvId);
					serverState =
						identifiableKindMap["chapterContent"].get(id as CCProvId)?.serverId ?? null;
					break;
				case "labelGroup":
					currentState = yield* idObjState("labelGroup", id as LGProvId);
					serverState =
						identifiableKindMap["labelGroup"].get(id as LGProvId)?.serverId ?? null;
					break;
				case "labelData":
					currentState = yield* idObjState("labelData", id as LDProvId);
					serverState =
						identifiableKindMap["labelData"].get(id as LDProvId)?.serverId ?? null;
					break;
				case "label":
					currentState = yield* idObjState("label", id as LProvId);
					serverState =
						existableKindMap["label"].get(id as LProvId)?.serverExists ?? null;
					break;
				default:
					return false;
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

	const reserveIdObjState = (kind: Kind, id: ProvTypes[Kind], desiredState: InFlightIdStatus) =>
		Effect.gen(function* () {
			const reserveable = yield* isReserveable(kind, id, desiredState);
			if (!reserveable) {
				return yield* Effect.fail(new NotReserveableException());
			}
			let entry:
				| {
						serverId: ServId | null;
						status: IdStatus;
						lockCount: number;
				  }
				| {
						serverExists: ServEx | null;
						status: IdStatus;
						lockCount: number;
				  }
				| undefined;
			switch (kind) {
				case "chapter":
					entry = identifiableKindMap["chapter"].get(id as CProvId);
					break;
				case "chapterContent":
					entry = identifiableKindMap["chapterContent"].get(id as CCProvId);
					break;
				case "labelGroup":
					entry = identifiableKindMap["labelGroup"].get(id as LGProvId);
					break;
				case "labelData":
					entry = identifiableKindMap["labelData"].get(id as LDProvId);
					break;
				case "label":
					entry = existableKindMap["label"].get(id as LProvId);
					break;
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

	const releaseIdObjState =
		(post: (status: InFlightIdStatus) => GroundIdStatus) =>
		(kind: Kind, id: ProvTypes[Kind]) => {
			let entry:
				| {
						serverExists: ServEx | null;
						status: IdStatus;
						lockCount: number;
				  }
				| {
						serverId: ServId | null;
						status: IdStatus;
						lockCount: number;
				  }
				| undefined;

			switch (kind) {
				case "chapter":
					entry = identifiableKindMap["chapter"].get(id as CProvId);
					break;
				case "chapterContent":
					entry = identifiableKindMap["chapterContent"].get(id as CCProvId);
					break;
				case "labelGroup":
					entry = identifiableKindMap["labelGroup"].get(id as LGProvId);
					break;
				case "labelData":
					entry = identifiableKindMap["labelData"].get(id as LDProvId);
					break;
				case "label":
					entry = existableKindMap["label"].get(id as LProvId);
					break;
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
			return Effect.succeed(ActionHappened(true));
		};

	const releaseIdObjStateOnSuccess = releaseIdObjState(exitStatus);
	const releaseIdObjStateOnFailure = releaseIdObjState(entryStatus);

	const gc = () => {
		identifiableKindMap.labelGroup.forEach((value, key) => {
			if (
				value.status === "deleted" ||
				value.status === "killed" ||
				value.status === "detached"
			) {
				identifiableKindMap.labelGroup.delete(key);
			}
		});
		identifiableKindMap.labelData.forEach((value, key) => {
			if (
				value.status === "deleted" ||
				value.status === "killed" ||
				value.status === "detached"
			) {
				identifiableKindMap.labelData.delete(key);
			}
		});
		identifiableKindMap.chapterContent.forEach((value, key) => {
			if (
				value.status === "deleted" ||
				value.status === "killed" ||
				value.status === "detached"
			) {
				identifiableKindMap.chapterContent.delete(key);
			}
		});
		identifiableKindMap.chapter.forEach((value, key) => {
			if (
				value.status === "deleted" ||
				value.status === "killed" ||
				value.status === "detached"
			) {
				identifiableKindMap.chapter.delete(key);
			}
		});
		existableKindMap.label.forEach((value, key) => {
			if (
				value.status === "deleted" ||
				value.status === "killed" ||
				value.status === "detached"
			) {
				existableKindMap.label.delete(key);
			}
		});
	};

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
		gc,
	};
}
