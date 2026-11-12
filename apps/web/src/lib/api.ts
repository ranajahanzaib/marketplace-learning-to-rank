export type Provider = {
  provider_id: string;
  display_name: string;
  headline: string;
  description: string;
  primary_category: string;
  specialties: string[];
  skills: string[];
  hourly_rate_usd: number;
  years_experience: number;
  city: string;
  country: string;
  remote_available: boolean;
  onsite_available: boolean;
  availability_status: string;
  average_rating: number | null;
  review_count: number;
  completed_projects: number;
  verified_status: boolean;
};
export type Result = {
  provider: Provider;
  score: number;
  rank: number;
  explanation: string[];
  feature_contributions: Record<string, number>;
  features: Record<string, number>;
};
export type SearchResponse = {
  results: Result[];
  eligible_count: number;
  candidate_counts: Record<string, number>;
  constraints_applied: string[];
  message?: string;
  timings_ms: Record<string, number>;
};
const API = "http://localhost:8000/api/v1";
export async function get<T>(path: string): Promise<T> {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<T>;
}
export async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(API + path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<T>;
}
export async function search(
  body: Record<string, unknown>,
  strategy: string,
  signal?: AbortSignal,
) {
  return getPostSearch(body, strategy, signal);
}
async function getPostSearch(
  body: Record<string, unknown>,
  strategy: string,
  signal?: AbortSignal,
) {
  const r = await fetch(`${API}/search?strategy=${strategy}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<SearchResponse>;
}
export async function compare(
  body: Record<string, unknown>,
  strategies = "rules,lambdamart",
) {
  return post<any>(
    `/search/compare?strategies=${encodeURIComponent(strategies)}`,
    body,
  );
}

export async function del(path: string) {
  const r = await fetch(API + path, { method: "DELETE" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
