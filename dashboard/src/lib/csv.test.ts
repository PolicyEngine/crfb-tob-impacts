import { describe, expect, test } from "bun:test";

import { csvCell, toCsvLine } from "./csv";

describe("csvCell", () => {
  test("passes plain values through untouched", () => {
    expect(csvCell("Tax 100% of Benefits")).toBe("Tax 100% of Benefits");
    expect(csvCell("-1658.83")).toBe("-1658.83");
  });

  test("quotes values containing commas", () => {
    expect(
      csvCell("85% Taxation, Replace Senior Deduction with $500 Credit"),
    ).toBe('"85% Taxation, Replace Senior Deduction with $500 Credit"');
  });

  test("escapes embedded quotes", () => {
    expect(csvCell('the "solvent" baseline')).toBe(
      '"the ""solvent"" baseline"',
    );
  });
});

describe("toCsvLine", () => {
  test("keeps one cell per column when a value contains a comma", () => {
    const line = toCsvLine([
      "85% Taxation, Replace Senior Deduction with $700 Credit",
      "2030",
      "12.34",
    ]);
    // A strict RFC 4180 reader splits on commas outside quotes.
    const parsed = line.match(/("([^"]|"")*"|[^,]*)(,|$)/g) ?? [];
    expect(line).toBe(
      '"85% Taxation, Replace Senior Deduction with $700 Credit",2030,12.34',
    );
    expect(parsed.slice(0, 3)).toHaveLength(3);
  });
});
