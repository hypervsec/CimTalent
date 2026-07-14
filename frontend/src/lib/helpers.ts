export function parseJsonPayload(value: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object")
    throw new Error("JSON nesnesi gerekli");
  return parsed as Record<string, unknown>;
}
export function renderRequirement(value: unknown): string {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const row = value as Record<string, unknown>;
    return String(row.label ?? row.value ?? row.type ?? JSON.stringify(row));
  }
  return "Belirsiz";
}
export function buckets(scores: number[]) {
  return [
    { name: "0–59", value: scores.filter((x) => x < 60).length },
    { name: "60–79", value: scores.filter((x) => x >= 60 && x < 80).length },
    { name: "80–100", value: scores.filter((x) => x >= 80).length },
  ];
}
export function distribution(values: Array<string | null | undefined>) {
  return Object.entries(
    values.reduce<Record<string, number>>((all, value) => {
      const key = value || "Belirsiz";
      all[key] = (all[key] ?? 0) + 1;
      return all;
    }, {}),
  ).map(([name, value]) => ({ name, value }));
}
