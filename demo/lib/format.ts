export function fixed(value: number, places = 4): string {
  const bounded = Math.min(Math.max(places, 0), 4);
  const text = value.toFixed(bounded);
  return text === "-" + (0).toFixed(bounded) ? (0).toFixed(bounded) : text;
}

export function signed(value: number, places = 4): string {
  const text = fixed(Math.abs(value), places);
  if (Number(text) === 0) return "+" + text;
  return (value < 0 ? "\u2212" : "+") + text;
}

export function exactZero(value: number): string {
  return value === 0 ? "+0.000000" : signed(value, 4);
}

export function percent(value: number): string {
  return `${Math.round(value * 100)} %`;
}

export function shortId(id: string): string {
  return id.slice(0, 6);
}
