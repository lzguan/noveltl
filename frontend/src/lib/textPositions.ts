export function createTextPositionMap(text: string) {
	const utf16Offsets = [0];
	const codePointOffsets = new Map<number, number>([[0, 0]]);
	let utf16Offset = 0;
	for (const char of text) {
		utf16Offset += char.length;
		codePointOffsets.set(utf16Offset, utf16Offsets.length);
		utf16Offsets.push(utf16Offset);
	}
	return {
		toUtf16(pos: number): number {
			const offset = utf16Offsets[pos];
			if (!Number.isInteger(pos) || offset === undefined)
				throw new RangeError(`Invalid code-point position: ${pos}`);
			return offset;
		},
		toCodePoint(pos: number): number {
			const offset = codePointOffsets.get(pos);
			if (offset === undefined) throw new RangeError(`Invalid UTF-16 boundary: ${pos}`);
			return offset;
		},
	};
}

export function codePointToUtf16(text: string, pos: number): number {
	return createTextPositionMap(text).toUtf16(pos);
}

export function utf16ToCodePoint(text: string, pos: number): number {
	return createTextPositionMap(text).toCodePoint(pos);
}

export function codePointLength(text: string): number {
	return Array.from(text).length;
}
