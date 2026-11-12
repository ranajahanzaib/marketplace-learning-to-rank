import { describe, expect, it } from "vitest";
import { rankChanges } from "./ranking";
const row = (provider_id: string, rank: number) => ({
  provider: { provider_id },
  rank,
});
describe("rankChanges", () => {
  it("reports promoted, demoted, entered, and exited candidates", () => {
    expect(
      rankChanges(
        [row("a", 1), row("b", 2), row("c", 3)],
        [row("b", 1), row("d", 2), row("a", 3)],
      ),
    ).toEqual([
      { providerId: "b", from: 2, to: 1, change: 1, status: "retained" },
      { providerId: "d", from: null, to: 2, change: null, status: "entered" },
      { providerId: "a", from: 1, to: 3, change: -2, status: "retained" },
      { providerId: "c", from: 3, to: null, change: null, status: "left" },
    ]);
  });
  it("keeps stable ranks neutral", () =>
    expect(rankChanges([row("a", 1)], [row("a", 1)])[0].change).toBe(0));
});
