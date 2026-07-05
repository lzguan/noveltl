import { Brand, Effect } from "effect";
import type { Prov } from "./helperTypes";
import type {
	ResourceConflictException,
	NotFoundException,
	NotReserveableException,
} from "./errors";
import type {
	AutoLabel,
	AutoLabelMeta,
	AutoLabelRunOutput,
	Chapter,
	ChapterContent,
	Label,
	LabelData,
	LabelGroup,
} from "@/api/models";
import type { AnyReservation } from "./requestTypes";

/**
 * A provisional id is a string that is used as a placeholder for a corresponding server id that may or may not exist yet.
 */
export type ProvId = Prov<string>;
export const ProvId = Brand.nominal<ProvId>();

/**
 * A server id is a string that is used to identify a resource on the server.
 */
export type ServId = string & Brand.Brand<"ServId">;
export const ServId = Brand.nominal<ServId>();

/**
 * A server existence flag is a certificate that indicates that a resource exists on the server.
 */
export type ServEx = true & Brand.Brand<"ServEx">;
export const ServEx = Brand.nominal<ServEx>();

// Provisional ids for data types
export type LGProvId = ProvId & Brand.Brand<"LG">;
export const LGProvId = Brand.nominal<LGProvId>();
export type LDProvId = ProvId & Brand.Brand<"LD">;
export const LDProvId = Brand.nominal<LDProvId>();
export type CCProvId = ProvId & Brand.Brand<"CC">;
export const CCProvId = Brand.nominal<CCProvId>();
export type CProvId = ProvId & Brand.Brand<"C">;
export const CProvId = Brand.nominal<CProvId>();
export type LProvId = ProvId & Brand.Brand<"L">;
export const LProvId = Brand.nominal<LProvId>();
export type AProvId = ProvId & Brand.Brand<"A">;
export const AProvId = Brand.nominal<AProvId>();
export type ALRProvId = ProvId & Brand.Brand<"ALR">;
export const ALRProvId = Brand.nominal<ALRProvId>();

// server ids
export type LGServId = ServId & Brand.Brand<"LG">;
export const LGServId = Brand.nominal<LGServId>();
export type LDServId = ServId & Brand.Brand<"LD">;
export const LDServId = Brand.nominal<LDServId>();
export type CCServId = ServId & Brand.Brand<"CC">;
export const CCServId = Brand.nominal<CCServId>();
export type CServId = ServId & Brand.Brand<"C">;
export const CServId = Brand.nominal<CServId>();
export type LServEx = ServEx & Brand.Brand<"L">;
export const LServEx = Brand.nominal<LServEx>();
export type AServId = ServId & Brand.Brand<"A">;
export const AServId = Brand.nominal<AServId>();
export type ALRServId = ServId & Brand.Brand<"ALR">;
export const ALRServId = Brand.nominal<ALRServId>();

export type ProvTypes = {
	labelGroup: LGProvId;
	labelData: LDProvId;
	chapterContent: CCProvId;
	chapter: CProvId;
	label: LProvId;
	autoLabel: AProvId;
	autoLabelRun: ALRProvId;
};

export const ProvTypes = {
	labelGroup: LGProvId,
	labelData: LDProvId,
	chapterContent: CCProvId,
	chapter: CProvId,
	label: LProvId,
	autoLabel: AProvId,
	autoLabelRun: ALRProvId,
} as const;

export type ServTypes = {
	labelGroup: LGServId;
	labelData: LDServId;
	chapterContent: CCServId;
	chapter: CServId;
	label: LServEx;
	autoLabel: AServId;
	autoLabelRun: ALRServId;
};

export const ServTypes = {
	labelGroup: LGServId,
	labelData: LDServId,
	chapterContent: CCServId,
	chapter: CServId,
	label: LServEx,
	autoLabel: AServId,
	autoLabelRun: ALRServId,
} as const;

// Provisional data types
type ProvDataT<T, key extends Record<string, unknown>> = Prov<
	Omit<T, keyof key> & { [K in keyof key]: key[K] }
>;
export type ProvChapter = ProvDataT<Chapter, { chapterId: CProvId }>;
export type ProvChapterContent = ProvDataT<
	ChapterContent,
	{ chapterId: CProvId; chapterContentId: CCProvId }
>;
export type ProvLabelData = ProvDataT<
	LabelData,
	{ labelDataId: LDProvId; chapterContentId: CCProvId; labelGroupId: LGProvId }
>;
export type ProvLabel = ProvDataT<Label, { labelDataId: LDProvId; labelId: LProvId }>;
export type ProvLabelGroup = ProvDataT<LabelGroup, { labelGroupId: LGProvId }>;
export type ProvAutoLabel = ProvDataT<
	AutoLabel,
	{ chapterContentId: CCProvId; autoLabelId: AProvId; runId: ALRProvId }
>;
export type ProvAutoLabelMeta = ProvDataT<
	AutoLabelMeta,
	{ chapterContentId: CCProvId; autoLabelId: AProvId; runId: ALRProvId }
>;
export type ProvAutoLabelMetaWithCid = {
	autoLabelMeta: ProvAutoLabelMeta;
	chapterId: CProvId;
};
export type ProvAutoLabelRun = ProvDataT<AutoLabelRunOutput, { runId: ALRProvId }>;

/**
 * An id status is a status associated with a provisional id. Id statuses are split into two categories:
 * - in-flight: indicates that a request associated with this id is currently being in-flight or being processed on the backend.
 * - ground: not in-flight.
 *
 * Id statuses are further subcategorized into more specific statuses that have more semantic meaning along with fixed state transitions. Specified further below.
 */
export type IdStatus = InFlightIdStatus | GroundIdStatus;

/**
 * In-flight id statuses indicate that a request associated with this id is currently being in-flight or being processed on the backend. The specific in-flight statuses are as follows:
 * - creating: the resource corresponding to this id is being created on the backend.
 * - updating: the resource corresponding to this id is being updated on the backend.
 * - idUpdating: the server id corresponding to this provisional id is being updated on the backend.
 * - deleting: the resource corresponding to this id is being deleted on the backend.
 * - locked: the resource corresponding to this id is being read-locked. This is to ensure that requests that require the resource to not be modified on the backend before they are sent to the backend can reserve the id to prevent other requests from modifying the resource.
 * - loading: the resource corresponding to this id is being loaded from the backend. This represents resources that the frontend knows exists on the backend but does not have up-to-date information on.
 * - detaching: Special case. Signals that the frontend intends to stop tracking this id.
 * - killing: Special case. the resource corresponding to this id has not been created/loaded on the backend yet, and the frontend intends to stop tracking this id.
 */
export type InFlightIdStatus =
	| "creating"
	| "updating"
	| "idUpdating"
	| "deleting"
	| "locked"
	| "loading"
	| "detaching"
	| "killing";

/**
 * Ground id statuses indicate that a resource is not currently being modified on the backend. The specific ground statuses are as follows:
 * - pending: the resource corresponding to this id is not tracked on the frontend yet, but is expected to be tracked in the future.
 * - clean: the resource corresponding to this id is being tracked on the frontend, and there are currently no in-flight requests associated with this id.
 * - deleted: the resource corresponding to this id has been deleted on the backend.
 * - detached: the frontend has stopped tracking this id, but it has not been deleted on the backend.
 * - killed: the resource corresponding to this id has not been created on the backend yet, and the frontend has stopped tracking this id.
 */
export type GroundIdStatus = "pending" | "clean" | "deleted" | "detached" | "killed";

/**
 * The state transitions are defined in such a way that for each in-flight status, there is exactly one ground state that can transition to it and exactly one ground state that it can transition to. We call these ground statuses corresponding to an in-flight status the entry ground status and the exit ground status, respectively.
 *
 * We define these state transitions as follows:
 *
 * TODO: add state transition diagram.
 *
 * - Note: on failure, in-flight statuses transition back to their entry ground status, while on success, they transition to their exit ground status.
 * - Note: the "locked" in-flight status can be reserved multiple times and only transitions back to "clean" once all locks are released. See more details in the implementation of the ID repository.
 */

/**
 * Given an in-flight status, returns the corresponding entry ground status that can transition to this in-flight status.
 */
export function entryStatus(status: InFlightIdStatus): GroundIdStatus {
	if (status === "creating" || status === "loading" || status === "killing") {
		return "pending";
	}
	return "clean";
}

/**
 * Given an in-flight status, returns the corresponding exit ground status that this in-flight status can transition to.
 */
export function exitStatus(status: InFlightIdStatus): GroundIdStatus {
	if (
		status === "creating" ||
		status === "updating" ||
		status === "idUpdating" ||
		status === "locked" ||
		status === "loading"
	) {
		return "clean";
	} else if (status === "detaching") {
		return "detached";
	} else if (status === "killing") {
		return "killed";
	}
	return "deleted";
}

/**
 * Certain ground id statuses are considered "terminal" in the sense that they cannot transition to any other ground status. These terminal statuses are as follows:
 * - deleted: the resource corresponding to this id has been deleted on the backend.
 * - detached: the frontend has stopped tracking this id, but it has not been deleted on the backend.
 * - killed: the resource corresponding to this id has not been created on the backend yet, and the frontend has stopped tracking this id.
 */
export function isTerminal(status: IdStatus): boolean {
	return status === "deleted" || status === "detached" || status === "killed";
}

/**
 * Type guard for checking if an id status is an in-flight status.
 */
export function isInFlight(status: IdStatus): status is InFlightIdStatus {
	return (
		status === "creating" ||
		status === "updating" ||
		status === "idUpdating" ||
		status === "deleting" ||
		status === "locked" ||
		status === "detaching" ||
		status === "loading" ||
		status === "killing"
	);
}

/**
 * A kind is a category of resource that a provisional id can correspond to. There are two main categories of kinds: identifiable kinds and existable kinds. Identifiable kinds are resources where the frontend tracks the server ids, while existable kinds are resources where the frontend does not track the server ids.
 */

export const identifiableKinds = [
	"labelGroup",
	"labelData",
	"chapterContent",
	"chapter",
	"autoLabel",
	"autoLabelRun",
] as const;
export const existableKinds = ["label"] as const;
export const kinds = [...identifiableKinds, ...existableKinds] as const;

export type Kind = (typeof kinds)[number];
export type IdentifiableKind = (typeof identifiableKinds)[number];
export type ExistableKind = (typeof existableKinds)[number];

/**
 * Type to certify that some function that might do nothing did in fact do something. Used for functions where it is not desirable to throw an error when the function fails to do something.
 */
export type ActionHappened = boolean & Brand.Brand<"ActionHappened">;
export const ActionHappened = Brand.nominal<ActionHappened>();

export type ProvServKind<K extends Kind> = {
	kind: K;
	provId: ProvTypes[K];
	servId: K extends IdentifiableKind ? ServTypes[K] : never;
};

export type AnyProvServKind<T extends Kind> = T extends Kind ? ProvServKind<T> : never;

export type DistributiveOmit<T, K extends keyof any> = T extends any ? Omit<T, K> : never;

/**
 * As the current data model stands, most objects have an underlying ID. In order to synchronize the IDs that appear on the frontend and backend without sacrificing client responsiveness, we need a way to bridge the gap between client-side IDs and server-side IDs. This repository serves as a central place to manage this mapping and the state of these IDs.
 *
 * The ID repository provides the following functionalities:
 *
 * Generating new provisional IDs for objects that are being created on the client side but have not yet been persisted to the server.
 * Binding provisional IDs to server IDs once the server responds with the created object.
 * Tracking the existence of objects that may not have a server ID but are known to exist on the server.
 * Managing the state of IDs to prevent race conditions and ensure that operations on objects are performed in a consistent manner.
 *
 * The way it does so is as follows:
 * - Each provisional ID is keyed using a combination of its kind (e.g., "labelGroup", "labelData", "chapterContent") and a unique identifier (e.g., "provisional-1", "provisional-2", etc.).
 * - For each provisional ID, we associate it with a server ID (possibly null if it has not yet been created on the server) and a status (see types.ts for the possible statuses and state transitions).
 * - Any given provisional ID can be reserved for a specific state transition (e.g., from "pending" to "creating", from "clean" to "updating", etc.) if it is currently in the appropriate state and has the appropriate server ID existence status.
 * - Once an ID is reserved for a state transition, it cannot be reserved for another transition until it is released. The exception to this is the "locked" state, which can be reserved multiple times and only transitions back to "clean" once all locks are released.
 * - The repository provides methods to release reserved states on both success and failure, which will transition the ID to the appropriate next state based on the outcome of the operation.
 *
 * By centralizing this logic in a repository, we can ensure that all components that need to interact with IDs do so in a consistent manner, reducing the likelihood of bugs and race conditions related to ID management.
 */

export interface IDRepository {
	/**
	 * Create a new id and manage it in the repository.
	 */
	newId(kind: "chapter"): ProvTypes["chapter"];
	newId(kind: "chapterContent"): ProvTypes["chapterContent"];
	newId(kind: "labelGroup"): ProvTypes["labelGroup"];
	newId(kind: "labelData"): ProvTypes["labelData"];
	newId(kind: "label"): ProvTypes["label"];
	newId(kind: "autoLabel"): ProvTypes["autoLabel"];
	newId(kind: "autoLabelRun"): ProvTypes["autoLabelRun"];

	/**
	 * Create a new id, bind it to the given server id, and manage it in the repository. If duplicate server id is detected that is clean or locked, no-op and return that id. If duplicate is found that is not clean or locked, throw ResourceConflictException.
	 */
	newIdAndBindId(
		params: Omit<ProvServKind<"chapter">, "provId">,
	): Effect.Effect<ProvTypes["chapter"], ResourceConflictException>;
	newIdAndBindId(
		params: Omit<ProvServKind<"chapterContent">, "provId">,
	): Effect.Effect<ProvTypes["chapterContent"], ResourceConflictException>;
	newIdAndBindId(
		params: Omit<ProvServKind<"labelGroup">, "provId">,
	): Effect.Effect<ProvTypes["labelGroup"], ResourceConflictException>;
	newIdAndBindId(
		params: Omit<ProvServKind<"labelData">, "provId">,
	): Effect.Effect<ProvTypes["labelData"], ResourceConflictException>;
	newIdAndBindId(
		params: Omit<ProvServKind<"autoLabel">, "provId">,
	): Effect.Effect<ProvTypes["autoLabel"], ResourceConflictException>;
	newIdAndBindId(
		params: Omit<ProvServKind<"autoLabelRun">, "provId">,
	): Effect.Effect<ProvTypes["autoLabelRun"], ResourceConflictException>;

	/**
	 * Create a new id and bind it to the given server existence flag, and manage it in the repository.
	 */
	newIdAndBindExists(
		params: Omit<ProvServKind<"label">, "provId" | "servId">,
	): Effect.Effect<ProvTypes["label"]>;

	/**
	 * Get the server id corresponding to a provisional id. If server id has not been bound yet, return null.
	 */
	getServerId(
		params: Omit<ProvServKind<"chapter">, "servId">,
	): Effect.Effect<CServId | null, NotFoundException>;
	getServerId(
		params: Omit<ProvServKind<"chapterContent">, "servId">,
	): Effect.Effect<CCServId | null, NotFoundException>;
	getServerId(
		params: Omit<ProvServKind<"labelGroup">, "servId">,
	): Effect.Effect<LGServId | null, NotFoundException>;
	getServerId(
		params: Omit<ProvServKind<"labelData">, "servId">,
	): Effect.Effect<LDServId | null, NotFoundException>;
	getServerId(
		params: Omit<ProvServKind<"autoLabel">, "servId">,
	): Effect.Effect<AServId | null, NotFoundException>;
	getServerId(
		params: Omit<ProvServKind<"autoLabelRun">, "servId">,
	): Effect.Effect<ALRServId | null, NotFoundException>;
	/**
	 * Get the server existence flag corresponding to a provisional id. If existence flag has not been bound yet, return null.
	 */
	getServerExists(
		params: Omit<ProvServKind<"label">, "servId">,
	): Effect.Effect<LServEx | null, NotFoundException>;

	/**
	 * Bind a provisional id to a server id, so that the controller can update the corresponding entry with the new server id when it receives the signal from the request event. Raises ResourceConflictException if the server id is already bound to another provisional id or if the provisional id is already bound to a server id. Raises NotFoundException if the provisional id is not found in the repository.
	 */
	bindServerId(
		params: AnyProvServKind<IdentifiableKind>,
	): Effect.Effect<void, NotFoundException | ResourceConflictException>;
	/**
	 * Bind a provisional id to a server existence flag, so that the controller can update the corresponding entry with the new server existence flag when it receives the signal from the request event.
	 */
	bindServerExists(
		params: DistributiveOmit<AnyProvServKind<ExistableKind>, "servId">,
	): Effect.Effect<void, NotFoundException>;

	/**
	 * Get the current id status of a provisional id.
	 */
	idObjState(
		params: DistributiveOmit<AnyReservation<Kind>, "desiredState">,
	): Effect.Effect<IdStatus, NotFoundException>;

	/**
	 * Check if a provisional id is reserveable for a desired in-flight status. This works according to the state transition rules defined above.
	 */
	isReserveable(params: AnyReservation<Kind>): Effect.Effect<boolean, NotFoundException>;

	reserveIdObjState(
		params: AnyReservation<Kind>,
	): Effect.Effect<void, NotFoundException | NotReserveableException>;

	releaseIdObjStateOnSuccess(
		params: DistributiveOmit<AnyReservation<Kind>, "desiredState">,
	): Effect.Effect<ActionHappened, NotFoundException>;

	releaseIdObjStateOnFailure(
		params: DistributiveOmit<AnyReservation<Kind>, "desiredState">,
	): Effect.Effect<ActionHappened, NotFoundException>;

	queryProvId(
		params: Omit<ProvServKind<"labelGroup">, "provId">,
	): Effect.Effect<ProvTypes["labelGroup"] | null>;
	queryProvId(
		params: Omit<ProvServKind<"labelData">, "provId">,
	): Effect.Effect<ProvTypes["labelData"] | null>;
	queryProvId(
		params: Omit<ProvServKind<"chapterContent">, "provId">,
	): Effect.Effect<ProvTypes["chapterContent"] | null>;
	queryProvId(
		params: Omit<ProvServKind<"chapter">, "provId">,
	): Effect.Effect<ProvTypes["chapter"] | null>;
	queryProvId(
		params: Omit<ProvServKind<"autoLabel">, "provId">,
	): Effect.Effect<ProvTypes["autoLabel"] | null>;
	queryProvId(
		params: Omit<ProvServKind<"autoLabelRun">, "provId">,
	): Effect.Effect<ProvTypes["autoLabelRun"] | null>;

	gc(): void;
}
