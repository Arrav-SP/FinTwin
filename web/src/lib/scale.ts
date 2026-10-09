export type Domain = [number, number];

/** A padded [low, high] for a logarithmic axis, or null when there is nothing positive to show. */
export function logDomain(values: number[], padding = 1.35): Domain | null {
  const positive = values.filter((value) => Number.isFinite(value) && value > 0);
  if (positive.length === 0) return null;
  return [Math.min(...positive) / padding, Math.max(...positive) * padding];
}

/** Tick positions at 1, 2 and 5 times each power of ten that fall inside the domain. */
export function logTicks([low, high]: Domain): number[] {
  const ticks: number[] = [];
  for (let exponent = Math.floor(Math.log10(low)); exponent <= Math.ceil(Math.log10(high)); exponent++) {
    for (const step of [1, 2, 5]) {
      const tick = step * 10 ** exponent;
      if (tick >= low && tick <= high) ticks.push(Number(tick.toPrecision(1)));
    }
  }
  return ticks.length > 0 ? ticks : [Number(Math.sqrt(low * high).toPrecision(2))];
}
