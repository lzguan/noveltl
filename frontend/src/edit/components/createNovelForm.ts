import { NovelType, Visibility } from "@/api/models";

type CreateNovelFormValues = {
	languageCode: string;
	novelAuthor: string;
	novelDescription: string;
	novelTitle: string;
	novelType: NovelType;
	novelVisibility: Visibility;
	sourceWorkId: string | null;
};

const createNovelDefaultValues: CreateNovelFormValues = {
	languageCode: "",
	novelAuthor: "",
	novelDescription: "",
	novelTitle: "",
	novelType: NovelType.original,
	novelVisibility: Visibility.NUMBER_0,
	sourceWorkId: null,
};

function novelTypeFromValue(value: string): NovelType {
	switch (value) {
		case NovelType.translation:
			return NovelType.translation;
		case NovelType.other:
			return NovelType.other;
		default:
			return NovelType.original;
	}
}

function visibilityFromValue(value: string): Visibility {
	switch (value) {
		case String(Visibility.NUMBER_1):
			return Visibility.NUMBER_1;
		case String(Visibility.NUMBER_2):
			return Visibility.NUMBER_2;
		case String(Visibility.NUMBER_3):
			return Visibility.NUMBER_3;
		default:
			return Visibility.NUMBER_0;
	}
}

export {
	createNovelDefaultValues,
	novelTypeFromValue,
	visibilityFromValue,
	type CreateNovelFormValues,
};
