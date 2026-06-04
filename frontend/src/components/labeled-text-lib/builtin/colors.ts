/**
 * Packed RGB color encoded as 0xRRGGBB.
 */
export type Color = number;

function clampChannel(value: number): number {
  return Math.max(0, Math.min(255, Math.round(value)));
}

/**
 * Packs 8-bit RGB channels into a single integer color.
 */
export function rgb(red: number, green: number, blue: number): Color {
  return (clampChannel(red) << 16) | (clampChannel(green) << 8) | clampChannel(blue);
}

export function red(color: Color): number {
  return (color >> 16) & 0xff;
}

export function green(color: Color): number {
  return (color >> 8) & 0xff;
}

export function blue(color: Color): number {
  return color & 0xff;
}

/**
 * Converts a packed RGB color to a CSS hex color.
 */
export function toHex(color: Color): string {
  return `#${(color & 0xffffff).toString(16).padStart(6, "0")}`;
}

/**
 * Parses #RGB and #RRGGBB CSS hex strings into a packed RGB color.
 */
export function fromHex(hex: string): Color {
  const normalized = hex.trim().replace(/^#/, "");

  if (normalized.length === 3) {
    return rgb(
      Number.parseInt(normalized[0] + normalized[0], 16),
      Number.parseInt(normalized[1] + normalized[1], 16),
      Number.parseInt(normalized[2] + normalized[2], 16),
    );
  }

  if (normalized.length === 6) {
    const parsed = Number.parseInt(normalized, 16);
    if (Number.isNaN(parsed)) {
      throw new Error(`Invalid hex color: ${hex}`);
    }
    return parsed;
  }

  throw new Error(`Invalid hex color: ${hex}`);
}

/**
 * Averages colors channel-by-channel.
 */
export function averageColors(colors: Color[]): Color {
  if (colors.length === 0) {
    throw new Error("averageColors requires at least one color");
  }

  const total = colors.reduce(
    (accumulator, color) => ({
      red: accumulator.red + red(color),
      green: accumulator.green + green(color),
      blue: accumulator.blue + blue(color),
    }),
    { red: 0, green: 0, blue: 0 },
  );

  return rgb(total.red / colors.length, total.green / colors.length, total.blue / colors.length);
}

/**
 * Linearly interpolates between two colors channel-by-channel.
 * `weight = 0` returns `left`, `weight = 1` returns `right`.
 */
export function blendColors(left: Color, right: Color, weight: number = 0.5): Color {
  const clampedWeight = Math.max(0, Math.min(1, weight));
  const leftWeight = 1 - clampedWeight;

  return rgb(
    red(left) * leftWeight + red(right) * clampedWeight,
    green(left) * leftWeight + green(right) * clampedWeight,
    blue(left) * leftWeight + blue(right) * clampedWeight,
  );
}

export function generateRandomColor(): Color {
  return Math.floor(Math.random() * 16777215);
}
