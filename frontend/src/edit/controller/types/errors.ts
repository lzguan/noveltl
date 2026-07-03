import { Data } from "effect";
import type { RequestKey } from "./requestTypes";
import type { TimeoutException } from "effect/Cause";
import type { CProvId, LGProvId, ProvId, ServId } from "./idTypes";

/**
 * Represents a cache conflict on the backend.
 */
export class CacheConflictException extends Data.TaggedError("CacheConflictException")<{
	requestKey: RequestKey;
}> {}

/**
 * Represents a missing cache entry on the backend.
 */
export class NoCacheEntryException extends Data.TaggedError("NoCacheEntryException")<{
	requestKey: RequestKey;
}> {}

/**
 * Represents failure to send a request to the backend.
 */
export class ConnectionException extends Data.TaggedError("ConnectionException")<{
	orig: unknown;
}> {}

/**
 * Represents a request that cannot be recovered from (e.g. due to unsynced/out of date data on the client).
 */
export class FatalException extends Data.TaggedError("FatalException")<{
	orig?: unknown;
}> {}

/**
 * Represents data that cannot be found within some data collection on the frontend.
 */
export class NotFoundException extends Data.TaggedError("NotFoundException")<{}> {}

/**
 * Represents an attempt to reserve an ID for a state transition that is not currently reserveable due to the current state of the ID and/or the existence status of the corresponding server ID.
 */
export class NotReserveableException extends Data.TaggedError("NotReserveableException")<{}> {}

/**
 * Represents a request that is still pending completion on the backend.
 */
export class PendingException extends Data.TaggedError("PendingException")<{}> {}

/**
 * Represents trying to perform an operation that duplicates an existing chapter number.
 */
export class DuplicateChapterNumException extends Data.TaggedError(
	"DuplicateChapterNumException",
)<{}> {}

export class DuplicateProvIdException extends Data.TaggedError("DuplicateProvIdException")<{
	id: ProvId;
}> {}

export class DuplicateServIdException extends Data.TaggedError("DuplicateServIdException")<{
	id: ServId;
}> {}

export class AlreadyOpenException extends Data.TaggedError("AlreadyOpenException")<{
	id: ProvId;
}> {}

export class LoadingException extends Data.TaggedError("LoadingException")<{ id: ProvId }> {}

export class ChapterLoadingException extends Data.TaggedError("ChapterLoadingException")<{
	chapterId: CProvId;
}> {}

export class LabelGroupLoadingException extends Data.TaggedError("LabelGroupLoadingException")<{
	labelGroupId: LGProvId;
}> {}

export class LabelDataLoadingException extends Data.TaggedError("LabelDataLoadingException")<{
	labelGroupId: LGProvId;
}> {}

/**
 * Union of errors that can occur at the request processing level. DM-level errors
 * (AlreadyOpenException, LoadingException, DuplicateIdException) are handled separately.
 */
export type AnyError =
	| FatalException
	| ConnectionException
	| CacheConflictException
	| NoCacheEntryException
	| NotFoundException
	| NotReserveableException
	| TimeoutException
	| PendingException
	| DuplicateChapterNumException;
