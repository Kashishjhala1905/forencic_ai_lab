import { describe, expect, it } from "vitest";
import { CATEGORY, fmtBytes, STAGES, typeLabel } from "./format";

describe("format utils", () => {
  it("formats bytes", () => { expect(fmtBytes(512)).toBe("512 B"); expect(fmtBytes(1536)).toBe("1.5 KB"); expect(fmtBytes(5 * 1048576)).toBe("5.0 MB"); });
  it("every risk category has label, icon and tone (not colour-only)", () => {
    for (const k of ["LOW", "MEDIUM", "HIGH", "INSUFFICIENT"]) expect(CATEGORY[k]).toMatchObject({ label: expect.any(String), icon: expect.any(String), tone: expect.any(String) });
  });
  it("maps doc types and ends stages with done", () => { expect(typeLabel("id_card")).toBe("Identity document"); expect(STAGES.at(-1)[0]).toBe("done"); });
});
