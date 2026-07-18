/**
 * RFC 4180 CSV writing. Two reform display names contain commas, so every
 * cell must be quoted when it holds a comma, quote, or newline — a bare
 * join(",") shifts all later columns (CRFB caught this in the export).
 */
export function csvCell(value: string): string {
  return /[",\n\r]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

export function toCsvLine(cells: string[]): string {
  return cells.map(csvCell).join(",");
}
