import { type StyleReducer } from "../core/segmenters";
import { type Style } from "../core/types";
import { averageColors, type Color } from "./colors";

export type ProductStyle<Styles extends readonly Style[]> = readonly [...Styles];

export function productReducer<const Styles extends readonly Style[]>(
  ...reducers: { [K in keyof Styles]: StyleReducer<Styles[K]> }
): StyleReducer<ProductStyle<Styles>> {
  return (styles) => {
    const result = reducers.map((reducer, index) => {
      const coordinateStyles = styles.map((style) => style[index]) as Styles[typeof index][];

      return reducer(coordinateStyles);
    });

    return result as unknown as ProductStyle<Styles>;
  };
}

export type ColorStyle = {
  color: Color;
} & Style;

export type UnderlineStyle = {
  underline: boolean;
} & Style;

export type BoldStyle = {
  bold: boolean;
} & Style;

export function makeColorStyleAverageReducer(defaultColor: Color): StyleReducer<ColorStyle> {
  return (styles) => {
    if (styles.length === 0) {
      return {
        color: defaultColor,
      };
    }

    return {
      color: averageColors(styles.map((style) => style.color)),
    };
  };
}

export function makeUnderlineStyleReducer(
  defaultUnderline: boolean = false,
): StyleReducer<UnderlineStyle> {
  return (styles) => ({
    underline: styles.length === 0 ? defaultUnderline : styles.some((style) => style.underline),
  });
}

export function makeBoldStyleReducer(defaultBold: boolean = false): StyleReducer<BoldStyle> {
  return (styles) => ({
    bold: styles.length === 0 ? defaultBold : styles.some((style) => style.bold),
  });
}

export type PriorityStyle<S extends Style> = {
  priority: number;
} & S;

export function priorityReducer<S extends Style>(
  reducer: StyleReducer<S>,
): StyleReducer<PriorityStyle<S>> {
  return (styles) => {
    if (styles.length === 0) {
      return {
        priority: Infinity,
        ...reducer([]),
      };
    }
    const minPriority = Math.min(...styles.map((style) => style.priority));
    const candidateStyles = styles.filter((style) => style.priority === minPriority);
    return {
      priority: minPriority,
      ...reducer(candidateStyles),
    };
  };
}
