export type RankedId = { provider: { provider_id: string }; rank: number };
export function rankChanges(before: RankedId[], after: RankedId[]) {
  const oldRank = new Map(
    before.map((row) => [row.provider.provider_id, row.rank]),
  );
  const newRank = new Map(
    after.map((row) => [row.provider.provider_id, row.rank]),
  );
  const ids = new Set([...oldRank.keys(), ...newRank.keys()]);
  return [...ids]
    .map((id) => ({
      providerId: id,
      from: oldRank.get(id) ?? null,
      to: newRank.get(id) ?? null,
      change:
        oldRank.has(id) && newRank.has(id)
          ? oldRank.get(id)! - newRank.get(id)!
          : null,
      status: !oldRank.has(id)
        ? "entered"
        : !newRank.has(id)
          ? "left"
          : "retained",
    }))
    .sort(
      (a, b) =>
        (a.to ?? Infinity) - (b.to ?? Infinity) ||
        a.providerId.localeCompare(b.providerId),
    );
}
