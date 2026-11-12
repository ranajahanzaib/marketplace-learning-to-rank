import {
  Activity,
  ArrowUpRight,
  BarChart3,
  ChevronRight,
  Clock3,
  Database,
  FlaskConical,
  MapPin,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  compare,
  del,
  get,
  post,
  Result,
  search,
  SearchResponse,
} from "./lib/api";
import { rankChanges } from "./lib/ranking";
import "./style.css";
type Page =
  | "Search Playground"
  | "Ranking Comparison"
  | "Evaluation Lab"
  | "Experiment Lab"
  | "Data & Models";
const pages: Page[] = [
  "Search Playground",
  "Ranking Comparison",
  "Evaluation Lab",
  "Experiment Lab",
  "Data & Models",
];
function App() {
  const [page, setPage] = useState<Page>("Search Playground"),
    [strategy, setStrategy] = useState("rules"),
    [compareA, setCompareA] = useState("rules"),
    [compareB, setCompareB] = useState("lambdamart"),
    [brief, setBrief] = useState(
      "Looking for a React and Next.js developer to improve SaaS onboarding",
    ),
    [category, setCategory] = useState("Software development"),
    [budget, setBudget] = useState("90"),
    [hard, setHard] = useState(false),
    [minExp, setMinExp] = useState(""),
    [remote, setRemote] = useState(true),
    [specialties, setSpecialties] = useState("React"),
    [skills, setSkills] = useState("TypeScript, Next.js"),
    [city, setCity] = useState(""),
    [country, setCountry] = useState(""),
    [locationRequired, setLocationRequired] = useState(false),
    [onsite, setOnsite] = useState(false),
    [available, setAvailable] = useState(false),
    [rows, setRows] = useState<Result[]>([]),
    [searchMeta, setSearchMeta] = useState<SearchResponse | null>(null),
    [selected, setSelected] = useState<Result | null>(null),
    [state, setState] = useState("idle"),
    [searchError, setSearchError] = useState(""),
    [inspect, setInspect] = useState<any>(null),
    [compareData, setCompareData] = useState<any>(null),
    [evalData, setEvalData] = useState<any>(null),
    [modelData, setModelData] = useState<any>(null),
    [experiment, setExperiment] = useState<any>(null),
    [experimentResult, setExperimentResult] = useState<any>(null),
    [experimentId, setExperimentId] = useState(
      "marketplace_learning_to_rank-demo",
    ),
    [sessions, setSessions] = useState(300),
    [simulationSeed, setSimulationSeed] = useState(42),
    [controlStrategy, setControlStrategy] = useState("rules"),
    [treatmentStrategy, setTreatmentStrategy] = useState("lambdamart"),
    [allocation, setAllocation] = useState(50),
    [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const query = () => ({
    text: brief,
    category,
    specialties: specialties
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean),
    skills: skills
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean),
    max_rate_usd: Number(budget) || undefined,
    hard_budget: hard,
    remote_preferred: remote ? true : undefined,
    min_experience: minExp ? Number(minExp) : undefined,
    city: city || undefined,
    country: country || undefined,
    location_required: locationRequired,
    onsite_required: onsite,
    must_be_available: available,
  });
  function chooseDemo(kind: string) {
    const demos: any = {
      budget: {
        brief:
          "Affordable React and Next.js developer for a SaaS onboarding project",
        category: "Software development",
        specialties: "React",
        skills: "TypeScript, Next.js",
        budget: "50",
        hard: true,
        remote: true,
        exp: "3",
      },
      cyber: {
        brief: "Experienced cybersecurity consultant for a security assessment",
        category: "Business services",
        specialties: "Cybersecurity",
        skills: "penetration testing, OWASP",
        budget: "130",
        hard: false,
        remote: true,
        exp: "6",
      },
      ux: {
        brief: "Remote UX research specialist to test a new product journey",
        category: "Design",
        specialties: "UX research",
        skills: "interviews, usability testing",
        budget: "90",
        hard: false,
        remote: true,
        exp: "4",
      },
      cloud: {
        brief:
          "Available backend and cloud infrastructure engineer for an AWS migration",
        category: "Software development",
        specialties: "Backend systems",
        skills: "AWS, Python, PostgreSQL",
        budget: "120",
        hard: false,
        remote: true,
        exp: "5",
      },
      new: {
        brief:
          "Qualified React specialist with a complete profile but no review history",
        category: "Software development",
        specialties: "React",
        skills: "TypeScript, Next.js",
        budget: "100",
        hard: false,
        remote: true,
        exp: "2",
      },
    };
    const d = demos[kind];
    setBrief(d.brief);
    setCategory(d.category);
    setSpecialties(d.specialties);
    setSkills(d.skills);
    setBudget(d.budget);
    setHard(d.hard);
    setRemote(d.remote);
    setMinExp(d.exp);
    setLocationRequired(false);
    setCity("");
    setCountry("");
    setOnsite(false);
    setAvailable(kind === "cloud");
  }
  async function runSearch(selectedStrategy = strategy) {
    controller.current?.abort();
    const c = new AbortController();
    controller.current = c;
    setSearchError("");
    setState("loading");
    try {
      const r = await search(query(), selectedStrategy, c.signal);
      setRows(r.results);
      setSearchMeta(r);
      setState(r.message ? "empty" : "ready");
    } catch (e) {
      if (!c.signal.aborted) {
        setState("error");
        setSearchError(e instanceof Error ? e.message : String(e));
        setRows([]);
      }
    }
  }
  async function runCompare() {
    setBusy(true);
    try {
      setCompareData(await compare(query(), `${compareA},${compareB}`));
    } catch (e) {
      setCompareData({ error: String(e) });
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (page === "Evaluation Lab")
      get("/evaluation/summary")
        .then(setEvalData)
        .catch(() => setEvalData(null));
    if (page === "Data & Models")
      Promise.all([get<any>("/models/current"), get<any>("/pipeline/status")])
        .then(([m, p]) => setModelData({ ...m, pipeline: p }))
        .catch(() => {});
    return () => controller.current?.abort();
  }, [page]);
  async function createExperiment() {
    setBusy(true);
    try {
      const c = await post("/experiments", {
        experiment_id: experimentId,
        experiment_name: "Rules versus learned ranking demo",
        control_strategy: controlStrategy,
        treatment_strategy: treatmentStrategy,
        allocation_percentage: allocation,
        randomization_unit: "visitor",
        experiment_salt: "marketplace_learning_to_rank-demo-salt-2026",
      });
      setExperiment(c);
      setExperimentResult(null);
    } catch (e) {
      setExperiment({ error: String(e) });
    } finally {
      setBusy(false);
    }
  }
  async function resetSimulation() {
    setBusy(true);
    try {
      await del(`/experiments/${experimentId}/simulation`);
      setExperimentResult(null);
    } catch (e) {
      setExperimentResult({ error: String(e) });
    } finally {
      setBusy(false);
    }
  }
  async function simulate() {
    setBusy(true);
    try {
      if (!experiment) throw new Error("Create an experiment first");
      await post(
        `/experiments/${experimentId}/simulate?sessions=${sessions}&seed=${simulationSeed}`,
        {},
      );
      setExperimentResult(await get(`/experiments/${experimentId}/results`));
    } catch (e) {
      setExperimentResult({ error: String(e) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <div className="mark">R</div>
          <div>
            <b>Marketplace Learning to Rank</b>
            <small>RANKING LAB</small>
          </div>
        </div>
        <nav className="nav">
          {pages.map((name, i) => (
            <button
              className={page === name ? "active" : ""}
              key={name}
              onClick={() => setPage(name)}
            >
              {
                [
                  <Search size={17} />,
                  <Activity size={17} />,
                  <BarChart3 size={17} />,
                  <FlaskConical size={17} />,
                  <Database size={17} />,
                ][i]
              }
              {name}
            </button>
          ))}
        </nav>
        <div className="side-note">
          <span className="dot" />
          LOCAL WORKSPACE<small>CPU inference · no commercial APIs</small>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <p className="eyebrow">MARKETPLACE SEARCH / {page.toUpperCase()}</p>
            <h1>
              {page === "Search Playground"
                ? "Find the right people for the work."
                : page}
            </h1>
            <p className="sub">
              {page === "Search Playground"
                ? "Explore how ranking strategies interpret the same brief."
                : "Inspect measured ranking behavior, models, and synthetic experiment evidence."}
            </p>
          </div>
          <span className="synthetic">● SYNTHETIC DEMO DATA</span>
        </header>
        {page === "Search Playground" && (
          <>
            <SearchForm
              brief={brief}
              setBrief={setBrief}
              category={category}
              setCategory={setCategory}
              budget={budget}
              setBudget={setBudget}
              hard={hard}
              setHard={setHard}
              minExp={minExp}
              setMinExp={setMinExp}
              remote={remote}
              setRemote={setRemote}
              specialties={specialties}
              setSpecialties={setSpecialties}
              skills={skills}
              setSkills={setSkills}
              city={city}
              setCity={setCity}
              country={country}
              setCountry={setCountry}
              locationRequired={locationRequired}
              setLocationRequired={setLocationRequired}
              onsite={onsite}
              setOnsite={setOnsite}
              available={available}
              setAvailable={setAvailable}
              runSearch={runSearch}
            />
            <div className="demo-row">
              <span>TRY A SCENARIO</span>
              {[
                ["budget", "Budget vs expertise"],
                ["cyber", "Rare cybersecurity"],
                ["ux", "Remote UX research"],
                ["cloud", "Available cloud engineer"],
                ["new", "New provider cold start"],
              ].map(([key, label]) => (
                <button key={key} onClick={() => chooseDemo(key)}>
                  {label}
                </button>
              ))}
            </div>
            <div className="content-head">
              <div>
                <h2>Matching providers</h2>
                <p>
                  {searchMeta
                    ? `${searchMeta.eligible_count} eligible · ${searchMeta.candidate_counts.union ?? 0} retrieved · ${searchMeta.timings_ms.total_server?.toFixed(1) ?? "—"} ms server time`
                    : "Run a query to inspect the local provider catalog"}
                </p>
              </div>
              <StrategyPicker
                strategy={strategy}
                onSelect={(s: string) => {
                  setStrategy(s);
                  runSearch(s);
                }}
              />
            </div>
            <Results
              rows={rows}
              state={state}
              error={searchError}
              runSearch={runSearch}
              setSelected={setSelected}
            />
          </>
        )}
        {page === "Ranking Comparison" && (
          <>
            <SearchForm
              brief={brief}
              setBrief={setBrief}
              category={category}
              setCategory={setCategory}
              budget={budget}
              setBudget={setBudget}
              hard={hard}
              setHard={setHard}
              minExp={minExp}
              setMinExp={setMinExp}
              remote={remote}
              setRemote={setRemote}
              specialties={specialties}
              setSpecialties={setSpecialties}
              skills={skills}
              setSkills={setSkills}
              city={city}
              setCity={setCity}
              country={country}
              setCountry={setCountry}
              locationRequired={locationRequired}
              setLocationRequired={setLocationRequired}
              onsite={onsite}
              setOnsite={setOnsite}
              available={available}
              setAvailable={setAvailable}
              runSearch={runCompare}
            />
            <div className="content-head">
              <div>
                <h2>Same candidate pool, different ordering</h2>
                <p>
                  Custom searches have no relevance labels; compare order and
                  observed feature contributions only.
                </p>
              </div>
              <button className="primary" onClick={runCompare} disabled={busy}>
                {busy ? "Comparing…" : "Compare strategies"}
              </button>
            </div>
            <div className="compare-controls">
              <label>
                STRATEGY A{" "}
                <select
                  value={compareA}
                  onChange={(e) => setCompareA(e.target.value)}
                >
                  <option value="rules">Rules</option>
                  <option value="semantic">Semantic</option>
                  <option value="lambdamart">LambdaMART</option>
                </select>
              </label>
              <label>
                STRATEGY B{" "}
                <select
                  value={compareB}
                  onChange={(e) => setCompareB(e.target.value)}
                >
                  <option value="rules">Rules</option>
                  <option value="semantic">Semantic</option>
                  <option value="lambdamart">LambdaMART</option>
                </select>
              </label>
            </div>
            <CompareView
              data={compareData}
              setSelected={setSelected}
              strategyA={compareA}
              strategyB={compareB}
            />
          </>
        )}
        {page === "Evaluation Lab" && <EvaluationView data={evalData} />}
        {page === "Data & Models" && <ModelsView data={modelData} />}
        {page === "Experiment Lab" && (
          <ExperimentView
            id={experimentId}
            setId={setExperimentId}
            sessions={sessions}
            setSessions={setSessions}
            seed={simulationSeed}
            setSeed={setSimulationSeed}
            control={controlStrategy}
            setControl={setControlStrategy}
            treatment={treatmentStrategy}
            setTreatment={setTreatmentStrategy}
            allocation={allocation}
            setAllocation={setAllocation}
            experiment={experiment}
            result={experimentResult}
            create={createExperiment}
            simulate={simulate}
            reset={resetSimulation}
            busy={busy}
          />
        )}
        <footer>
          Offline evaluation uses synthetic labels. Simulated experiment
          outcomes are not customer evidence or booking lift.
        </footer>
      </main>
      {selected && (
        <Inspector result={selected} close={() => setSelected(null)} />
      )}
    </div>
  );
}
function SearchForm(p: any) {
  return (
    <section className="search-card">
      <label>PROJECT BRIEF</label>
      <textarea
        aria-label="Project brief"
        value={p.brief}
        onChange={(e) => p.setBrief(e.target.value)}
      />
      <div className="filters">
        <div>
          <label>SERVICE CATEGORY</label>
          <select
            aria-label="Service category"
            value={p.category}
            onChange={(e) => p.setCategory(e.target.value)}
          >
            <option>Software development</option>
            <option>Design</option>
            <option>Marketing</option>
            <option>Business services</option>
          </select>
        </div>
        <div>
          <label>SPECIALTIES</label>
          <input
            className="small-input"
            value={p.specialties}
            onChange={(e) => p.setSpecialties(e.target.value)}
            aria-label="Comma separated specialties"
          />
        </div>
        <div>
          <label>SKILLS</label>
          <input
            className="small-input"
            value={p.skills}
            onChange={(e) => p.setSkills(e.target.value)}
            aria-label="Comma separated skills"
          />
        </div>
        <div>
          <label>MAX HOURLY RATE</label>
          <div className="rate">
            <span>$</span>
            <input
              aria-label="Maximum hourly rate in US dollars"
              value={p.budget}
              type="number"
              onChange={(e) => p.setBudget(e.target.value)}
            />
            <small>/ hr</small>
          </div>
        </div>
        <div>
          <label>MIN EXPERIENCE</label>
          <input
            aria-label="Minimum experience in years"
            className="small-input"
            type="number"
            min="0"
            max="80"
            value={p.minExp}
            placeholder="Any"
            onChange={(e) => p.setMinExp(e.target.value)}
          />
        </div>
        <div>
          <label>CITY / COUNTRY</label>
          <div className="location-fields">
            <input
              aria-label="City"
              value={p.city}
              placeholder="City"
              onChange={(e) => p.setCity(e.target.value)}
            />
            <input
              aria-label="Country"
              value={p.country}
              placeholder="Country"
              onChange={(e) => p.setCountry(e.target.value)}
            />
          </div>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={p.hard}
            onChange={(e) => p.setHard(e.target.checked)}
          />{" "}
          Hard budget cap
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={p.remote}
            onChange={(e) => p.setRemote(e.target.checked)}
          />{" "}
          Prefer remote
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={p.locationRequired}
            onChange={(e) => p.setLocationRequired(e.target.checked)}
          />{" "}
          Require exact location
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={p.onsite}
            onChange={(e) => p.setOnsite(e.target.checked)}
          />{" "}
          On-site required
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={p.available}
            onChange={(e) => p.setAvailable(e.target.checked)}
          />{" "}
          Must be available now
        </label>
        <button onClick={() => p.runSearch()}>
          <Search size={16} /> Search providers
        </button>
      </div>
    </section>
  );
}
function StrategyPicker(p: any) {
  return (
    <div className="strategy">
      {["rules", "semantic", "lambdamart"].map((s) => (
        <button
          className={p.strategy === s ? "chosen" : ""}
          onClick={() => p.onSelect(s)}
          key={s}
        >
          {s === "lambdamart" ? "LambdaMART" : s[0].toUpperCase() + s.slice(1)}
        </button>
      ))}
    </div>
  );
}
function Results(p: {
  rows: Result[];
  state: string;
  error: string;
  runSearch: () => void;
  setSelected: (r: Result) => void;
}) {
  if (p.state === "idle")
    return (
      <div className="welcome">
        <div className="welcome-icon">
          <Search />
        </div>
        <h3>Start with a project brief</h3>
        <p>Search calls the real local API and ranking pipeline.</p>
        <button onClick={() => p.runSearch()}>
          Run example search <ArrowUpRight size={15} />
        </button>
      </div>
    );
  if (p.state === "loading")
    return <div className="welcome">Searching the local provider catalog…</div>;
  if (p.state === "empty")
    return (
      <div className="welcome">
        <h3>No eligible providers</h3>
        <p>Relax a hard filter explicitly, then search again.</p>
      </div>
    );
  if (p.state === "error")
    return (
      <div className="welcome">
        <h3>Search unavailable</h3>
        <p>
          {p.error || "Check the API, model readiness, and local data setup."}
        </p>
      </div>
    );
  return (
    <>
      {p.rows.map((r) => (
        <ProviderRow
          r={r}
          key={r.provider.provider_id}
          onClick={() => p.setSelected(r)}
        />
      ))}
    </>
  );
}
function ProviderRow({ r, onClick }: { r: Result; onClick: () => void }) {
  return (
    <article
      className="provider"
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <div className="avatar">
        {r.provider.display_name
          .split(" ")
          .map((x) => x[0])
          .join("")
          .slice(0, 2)}
      </div>
      <div className="provider-main">
        <div className="provider-title">
          <h3>{r.provider.display_name}</h3>
          <span className="score">
            {r.score.toFixed(3)} <small>SCORE</small>
          </span>
        </div>
        <p className="headline">{r.provider.headline}</p>
        <div className="pills">
          {r.provider.specialties.map((x) => (
            <span key={x}>{x}</span>
          ))}
          {r.provider.skills.slice(0, 3).map((x) => (
            <span key={x}>{x}</span>
          ))}
        </div>
        <div className="meta">
          <span>
            <MapPin size={13} />
            {r.provider.city}, {r.provider.country}
          </span>
          <span>
            <Clock3 size={13} />
            {r.provider.years_experience} years
          </span>
          <span>
            <ShieldCheck size={13} />
            {r.provider.average_rating
              ? `${r.provider.average_rating.toFixed(1)} · `
              : ""}
            {r.provider.review_count} reviews
          </span>
          <span>{r.provider.availability_status}</span>
        </div>
        {r.explanation.length > 0 && (
          <p className="headline">{r.explanation.slice(0, 2).join(" · ")}</p>
        )}
      </div>
      <div className="rate-out">
        ${r.provider.hourly_rate_usd}
        <small>/ hour</small>
      </div>
    </article>
  );
}
function CompareView({
  data,
  setSelected,
  strategyA,
  strategyB,
}: {
  data: any;
  setSelected: (r: Result) => void;
  strategyA: string;
  strategyB: string;
}) {
  if (!data)
    return (
      <div className="welcome">Run the comparison to call the backend.</div>
    );
  if (data.error) return <div className="notice">{data.error}</div>;
  const entries = Object.entries(data.strategies ?? {}) as [string, any][];
  const moves = rankChanges(
    data.strategies?.[strategyA]?.results ?? [],
    data.strategies?.[strategyB]?.results ?? [],
  );
  return (
    <>
      <p className="callout">
        Retrieved candidates: {data.candidate_counts?.union ?? 0} · Same
        candidate pool is passed to both rankers.
      </p>
      <section className="panel">
        <h2>
          Rank movement · {strategyA} → {strategyB}
        </h2>
        {moves.map((m) => (
          <div className="compare-row" key={m.providerId}>
            <span>{m.providerId}</span>
            <small>
              {m.from === null ? "—" : `#${m.from}`} →{" "}
              {m.to === null ? "—" : `#${m.to}`}
            </small>
            <b>
              {m.change === null
                ? m.status
                : m.change > 0
                  ? `↑ ${m.change}`
                  : m.change < 0
                    ? `↓ ${Math.abs(m.change)}`
                    : "—"}
            </b>
          </div>
        ))}
      </section>
      <div className="comparison-grid">
        {entries.map(([name, payload]) => (
          <section className="panel" key={name}>
            <h2>{name === "lambdamart" ? "LambdaMART" : name}</h2>
            {payload.available === false ? (
              <p>{payload.reason}</p>
            ) : (
              payload.results?.map((r: Result) => (
                <div
                  className="compare-row"
                  role="button"
                  tabIndex={0}
                  key={r.provider.provider_id}
                  onClick={() => setSelected(r)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelected(r);
                    }
                  }}
                >
                  <b>#{r.rank}</b>
                  <span>{r.provider.display_name}</span>
                  <small>{r.score.toFixed(4)}</small>
                  <ChevronRight size={15} />
                </div>
              ))
            )}
          </section>
        ))}
      </div>
      <p className="sub">
        Strategy scores are relative to each model; raw score scales are not
        comparable. The backend reports the candidate pool counts for this
        request.
      </p>
    </>
  );
}
function EvaluationView({ data }: any) {
  const [failures, setFailures] = useState<any>(null),
    [detail, setDetail] = useState<any>(null),
    [benchmark, setBenchmark] = useState<any>(null),
    [deltas, setDeltas] = useState<any>(null),
    [labeledQueries, setLabeledQueries] = useState<any[]>([]);
  useEffect(() => {
    get("/evaluation/failures?limit=8")
      .then(setFailures)
      .catch(() => {});
    get("/evaluation/benchmark")
      .then(setBenchmark)
      .catch(() => {});
    get("/evaluation/deltas?limit=2000")
      .then(setDeltas)
      .catch(() => {});
    get("/evaluation/queries?limit=1000")
      .then((result: any) => setLabeledQueries(result.queries ?? []))
      .catch(() => {});
  }, []);
  if (!data)
    return (
      <div className="notice">
        Evaluation report unavailable. Run `marketplace_learning_to_rank
        evaluate` after the pipeline.
      </div>
    );
  return (
    <>
      <div className="callout">
        Synthetic held-out evaluation · {data.query_count} test queries ·
        relevance threshold ≥ {data.relevance_threshold}. Confidence intervals
        use query-level bootstrap (1,000 resamples).
      </div>
      <section className="panel">
        <h2>Strategy performance</h2>
        <MetricBars strategies={data.strategies} />
        <table>
          <thead>
            <tr>
              <th>Strategy</th>
              <th>NDCG@5</th>
              <th>NDCG@10 (95% CI)</th>
              <th>Recall@5</th>
              <th>Recall@10 (95% CI)</th>
              <th>Precision@10</th>
              <th>MRR@10</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(data.strategies ?? {}).map(([s, m]: any) => (
              <tr key={s}>
                <td>{s}</td>
                <td>{m["ndcg@5"].mean.toFixed(3)}</td>
                <td>
                  {m["ndcg@10"].mean.toFixed(3)} [
                  {m["ndcg@10"].lower.toFixed(3)},{" "}
                  {m["ndcg@10"].upper.toFixed(3)}]
                </td>
                <td>{m["recall@5"].mean.toFixed(3)}</td>
                <td>
                  {m["recall@10"].mean.toFixed(3)} [
                  {m["recall@10"].lower.toFixed(3)},{" "}
                  {m["recall@10"].upper.toFixed(3)}]
                </td>
                <td>{m["precision@10"].mean.toFixed(3)}</td>
                <td>{m["mrr@10"].mean.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>Retrieval and cold start</h2>
        <p>
          Candidate-union recall: {data.candidate_recall.mean.toFixed(3)} [
          {data.candidate_recall.lower.toFixed(3)},{" "}
          {data.candidate_recall.upper.toFixed(3)}]
        </p>
        <p>
          Recall by retrieval stage:{" "}
          {Object.entries(data.candidate_recall_by_retriever ?? {})
            .map(
              ([name, m]: any) =>
                `${name}: ${m.available ? m.mean.toFixed(3) : "unavailable"}`,
            )
            .join(" · ")}
        </p>
        <p>
          Eligible-candidate coverage:{" "}
          {data.eligible_candidate_coverage_mean.toFixed(3)} · zero-result rate:{" "}
          {(data.zero_result_rate * 100).toFixed(1)}%
        </p>
        <p>
          Unseen provider IDs held out from training:{" "}
          {data.unseen_provider_holdout?.heldout_provider_count ?? 0}
        </p>
        {Object.entries(data.unseen_provider?.by_strategy ?? {}).map(
          ([s, m]: any) => (
            <p key={s}>
              {s}: unseen-provider Recall@10 {m["recall@10"].mean.toFixed(3)} (
              {m.query_count} queries)
            </p>
          ),
        )}
      </section>
      <section className="panel">
        <h2>Paired differences versus rules</h2>
        <pre>{JSON.stringify(data.paired_differences_vs_rules, null, 2)}</pre>
      </section>
      <section className="panel">
        <h2>Recall curve</h2>
        <RecallCurve strategies={data.strategies} />
      </section>
      <section className="panel">
        <h2>Query level NDCG@10 changes</h2>
        {deltas?.queries ? (
          <DeltaHistogram rows={deltas.queries} />
        ) : (
          <p>Per-query delta report unavailable.</p>
        )}
      </section>
      <section className="panel">
        <h2>Segment performance</h2>
        <SegmentTable segments={data.segments} />
      </section>
      <section className="panel">
        <h2>Inspect a labeled held-out query</h2>
        <label>
          TEST QUERY
          <select
            aria-label="Labeled held-out query"
            value={detail?.query_id ?? ""}
            onChange={(e) => {
              if (e.target.value)
                get(`/evaluation/queries/${e.target.value}`).then(setDetail);
              else setDetail(null);
            }}
          >
            <option value="">Select a test query</option>
            {labeledQueries.map((query) => (
              <option value={query.query_id} key={query.query_id}>
                {query.query_id} · {query.text.slice(0, 100)}
              </option>
            ))}
          </select>
        </label>
      </section>
      <section className="panel">
        <h2>Largest learned-ranker regressions</h2>
        {failures?.worst_regressions?.map((r: any) => (
          <button
            className="failure"
            key={r.query_id}
            onClick={() =>
              get(`/evaluation/queries/${r.query_id}`).then(setDetail)
            }
          >
            {r.query_id} · delta NDCG {r.ndcg_delta_vs_rules.toFixed(3)}{" "}
            <ChevronRight size={14} />
          </button>
        ))}
      </section>
      {detail && (
        <section className="panel">
          <h2>Held-out query inspection · {detail.query_id}</h2>
          <p>{detail.query?.text}</p>
          <p>
            Strongly relevant provider IDs:{" "}
            {detail.relevant_provider_ids.join(", ") || "none"}
          </p>
          <pre>{JSON.stringify(detail.rank_changes, null, 2)}</pre>
        </section>
      )}
      <section className="panel">
        <h2>Measured inference latency</h2>
        {benchmark ? (
          <>
            <p>
              Warm in-process server timing · {benchmark.iterations} iterations
              · initialization {benchmark.initialization_ms.toFixed(1)} ms ·{" "}
              {benchmark.throughput_requests_per_second.toFixed(1)}{" "}
              requests/second
            </p>
            <table>
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>p50 (ms)</th>
                  <th>p95 (ms)</th>
                  <th>Samples</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(benchmark.stage_latency_ms).map(
                  ([stage, m]: any) => (
                    <tr key={stage}>
                      <td>{stage}</td>
                      <td>{m.p50_ms.toFixed(2)}</td>
                      <td>{m.p95_ms.toFixed(2)}</td>
                      <td>{m.count}</td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </>
        ) : (
          <p>
            Run `marketplace_learning_to_rank benchmark` to measure local
            latency.
          </p>
        )}
      </section>
    </>
  );
}
function MetricBars({ strategies }: any) {
  return (
    <div
      className="metric-bars"
      aria-label="Held-out NDCG and recall by strategy"
    >
      {Object.entries(strategies ?? {}).map(([name, metrics]: any) => (
        <div className="metric-bars-row" key={name}>
          <b>{name}</b>
          {[
            ["NDCG@10", metrics["ndcg@10"].mean],
            ["Recall@10", metrics["recall@10"].mean],
          ].map(([label, value]: any) => (
            <div className="metric-bar" key={label}>
              <span>{label}</span>
              <div>
                <i
                  style={{
                    width: `${Math.max(0, Math.min(100, Number(value) * 100))}%`,
                  }}
                />
              </div>
              <b>{Number(value).toFixed(3)}</b>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
function RecallCurve({ strategies }: any) {
  return (
    <table>
      <thead>
        <tr>
          <th>Strategy</th>
          <th>Recall@5</th>
          <th>Recall@10</th>
          <th>Recall@20</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(strategies ?? {}).map(([name, metrics]: any) => (
          <tr key={name}>
            <td>{name}</td>
            {[5, 10, 20].map((k) => (
              <td key={k}>{metrics[`recall@${k}`].mean.toFixed(3)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
function DeltaHistogram({ rows }: { rows: any[] }) {
  const bins = Array.from({ length: 10 }, (_, i) => ({
    low: -1 + i * 0.2,
    high: -0.8 + i * 0.2,
    count: 0,
  }));
  for (const row of rows) {
    const index = Math.min(9, Math.max(0, Math.floor((row.delta + 1) / 0.2)));
    bins[index].count++;
  }
  const max = Math.max(1, ...bins.map((bin) => bin.count));
  return (
    <>
      <p>
        {rows.length} held-out queries · negative values indicate LambdaMART
        regression versus rules.
      </p>
      <div
        className="histogram"
        role="img"
        aria-label={`Distribution of NDCG at 10 changes across ${rows.length} held-out queries`}
      >
        {bins.map((bin) => (
          <div
            className={`histogram-bin ${bin.high <= 0 ? "negative-bar" : "positive-bar"}`}
            key={bin.low.toFixed(1)}
            title={`${bin.low.toFixed(1)} to ${bin.high.toFixed(1)}: ${bin.count} queries`}
          >
            <span
              style={{ height: `${Math.max(2, (bin.count / max) * 100)}%` }}
            />
            <small>{bin.low.toFixed(1)}</small>
          </div>
        ))}
      </div>
      <p>
        Queries: {rows.filter((row) => row.delta < 0).length} regressed ·{" "}
        {rows.filter((row) => row.delta === 0).length} unchanged ·{" "}
        {rows.filter((row) => row.delta > 0).length} improved
      </p>
    </>
  );
}
function SegmentTable({ segments }: any) {
  const rows = Object.entries(segments ?? {}).flatMap(
    ([segment, strategies]: any) =>
      Object.entries(strategies).map(([strategy, metrics]: any) => ({
        segment,
        strategy,
        ...metrics,
      })),
  );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Segment</th>
            <th>Strategy</th>
            <th>Queries</th>
            <th>NDCG@10</th>
            <th>Recall@10</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.segment}-${row.strategy}`}>
              <td>{row.segment.replaceAll("_", " ")}</td>
              <td>{row.strategy}</td>
              <td>{row.query_count}</td>
              <td>{row["ndcg@10"]?.mean.toFixed(3) ?? "—"}</td>
              <td>{row["recall@10"]?.mean.toFixed(3) ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function ModelsView({ data }: any) {
  const [importance, setImportance] = useState<any>(null);
  useEffect(() => {
    get("/models/importance")
      .then(setImportance)
      .catch(() => setImportance(null));
  }, []);
  if (!data)
    return (
      <div className="notice">Model and pipeline metadata unavailable.</div>
    );
  return (
    <>
      <section className="panel">
        <h2>Pipeline status</h2>
        {Object.entries(data.pipeline?.stages ?? {}).map(([key, value]) => (
          <div className="status-row" key={key}>
            <span className={value ? "dot" : "dot off"} />
            {key.replaceAll("_", " ")}
            <b>{value ? "ready" : "not built"}</b>
          </div>
        ))}
      </section>
      <section className="panel">
        <h2>Dataset overview</h2>
        {data.dataset ? (
          <>
            <p>
              {data.dataset.provider_count} providers ·{" "}
              {data.dataset.query_count} queries · {data.dataset.judgment_count}{" "}
              judgments
            </p>
            <p>
              Train / validation / test:{" "}
              {Object.entries(data.dataset.split_query_counts ?? {})
                .map(([key, value]) => `${key} ${value}`)
                .join(" · ")}
            </p>
            <p>
              Profiles with no reviews: {data.dataset.cold_start_provider_count}{" "}
              ({(data.dataset.cold_start_provider_fraction * 100).toFixed(1)}%)
              · unseen provider holdout:{" "}
              {data.dataset.unseen_provider_holdout_count}
            </p>
            <p>
              Label grades: {JSON.stringify(data.dataset.label_counts)} · Mean
              eligible-universe judgment coverage:{" "}
              {data.dataset.mean_judgment_coverage_of_eligible_universe.toFixed(
                3,
              )}
            </p>
            <p>
              Hourly rates USD: min {data.dataset.hourly_rate_usd.min} · median{" "}
              {data.dataset.hourly_rate_usd.median} · max{" "}
              {data.dataset.hourly_rate_usd.max}
            </p>
            <p>
              Budget distribution:{" "}
              {Object.entries(data.dataset.hourly_rate_usd.distribution ?? {})
                .map(([band, count]) => `${band}: ${count}`)
                .join(" · ")}
            </p>
            <h3>Provider categories</h3>
            <pre>
              {JSON.stringify(data.dataset.provider_category_counts, null, 2)}
            </pre>
            <h3>Rating and availability distributions</h3>
            <pre>
              {JSON.stringify(
                {
                  ratings: data.dataset.rating_counts,
                  availability: data.dataset.availability_counts,
                },
                null,
                2,
              )}
            </pre>
          </>
        ) : (
          <p>Run dataset validation to prepare an overview.</p>
        )}
      </section>
      <section className="panel">
        <h2>Current model</h2>
        <p>
          Semantic encoder:{" "}
          {data.semantic_available
            ? "all-MiniLM-L6-v2 loaded"
            : "not available locally"}
        </p>
        <p>
          LambdaMART:{" "}
          {data.lambdamart_available
            ? "loaded and schema checked"
            : "not loaded"}
        </p>
        {data.model_error && <div className="notice">{data.model_error}</div>}
        {data.model && <pre>{JSON.stringify(data.model, null, 2)}</pre>}
        {importance && (
          <>
            <h3>Global feature importance · split gain</h3>
            <p>Associational model importance; not causal.</p>
            {importance.features.slice(0, 12).map((f: any) => (
              <div className="contribution" key={f.name}>
                <span>{f.name}</span>
                <b>{Number(f.gain).toFixed(1)}</b>
              </div>
            ))}
          </>
        )}
      </section>
    </>
  );
}
function ExperimentView(p: any) {
  return (
    <>
      <div className="callout warning">
        Synthetic traffic — not real customer evidence. Simulated experiments
        validate instrumentation and explore behavior; they do not demonstrate
        actual conversion improvements.
      </div>
      <section className="panel">
        <h2>Experiment configuration</h2>
        <div className="experiment-controls">
          <label>
            CONTROL STRATEGY
            <select
              value={p.control}
              onChange={(e) => p.setControl(e.target.value)}
            >
              <option value="rules">Rules</option>
              <option value="semantic">Semantic</option>
              <option value="lambdamart">LambdaMART</option>
            </select>
          </label>
          <label>
            TREATMENT STRATEGY
            <select
              value={p.treatment}
              onChange={(e) => p.setTreatment(e.target.value)}
            >
              <option value="rules">Rules</option>
              <option value="semantic">Semantic</option>
              <option value="lambdamart">LambdaMART</option>
            </select>
          </label>
          <label>
            TREATMENT ALLOCATION %
            <input
              type="number"
              min="1"
              max="99"
              value={p.allocation}
              onChange={(e) => p.setAllocation(Number(e.target.value))}
            />
          </label>
        </div>
        <p>
          Randomization unit: visitor · Persistent assignment by stable
          experiment hash.
        </p>
        <label>EXPERIMENT ID</label>
        <input
          aria-label="EXPERIMENT ID"
          className="wide-input"
          value={p.id}
          onChange={(e) => p.setId(e.target.value)}
        />
        <button className="primary" onClick={p.create} disabled={p.busy}>
          {p.busy ? "Working…" : "Create persistent experiment"}
        </button>
        {p.experiment?.error && (
          <div className="notice">{p.experiment.error}</div>
        )}
        {p.experiment && !p.experiment.error && (
          <p>
            Created {p.experiment.experiment_id} · assignment persists by
            visitor ID
          </p>
        )}
      </section>
      <section className="panel">
        <h2>Generate synthetic sessions</h2>
        <div className="experiment-controls">
          <label>
            SESSIONS (MAX 10,000)
            <input
              aria-label="SESSIONS (MAX 10,000)"
              className="wide-input"
              type="number"
              min="1"
              max="10000"
              value={p.sessions}
              onChange={(e) => p.setSessions(Number(e.target.value))}
            />
          </label>
          <label>
            SIMULATION SEED
            <input
              aria-label="SIMULATION SEED"
              className="wide-input"
              type="number"
              value={p.seed}
              onChange={(e) => p.setSeed(Number(e.target.value))}
            />
          </label>
        </div>
        <button
          className="primary"
          onClick={p.simulate}
          disabled={p.busy || !p.experiment}
        >
          {p.busy ? "Simulating…" : "Run deterministic simulation"}
        </button>
        <button
          className="secondary"
          onClick={p.reset}
          disabled={p.busy || !p.experiment}
        >
          Reset simulated data
        </button>
        {p.result?.error && <div className="notice">{p.result.error}</div>}
        {p.result?.metrics && (
          <>
            <p>{p.result.warning}</p>
            <p>
              Exposure counts: control {p.result.allocation_counts.control} ·
              treatment {p.result.allocation_counts.treatment} · SRM p≈
              {p.result.sample_ratio_mismatch.p_value_approx.toFixed(3)} (
              {p.result.sample_ratio_mismatch.flagged
                ? "flagged"
                : "not flagged"}
              )
            </p>
            <p>
              Event counts:{" "}
              {Object.entries(p.result.event_counts ?? {})
                .map(([name, count]) => `${name.replaceAll("_", " ")} ${count}`)
                .join(" · ")}
            </p>
            <details className="timeline">
              <summary>Recent simulated event timeline</summary>
              <ol>
                {(p.result.event_timeline ?? []).map(
                  (event: any, index: number) => (
                    <li key={`${event.timestamp}-${index}`}>
                      <time>
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </time>{" "}
                      {event.event_type.replaceAll("_", " ")} · {event.variant}{" "}
                      · {event.visitor_id}
                    </li>
                  ),
                )}
              </ol>
            </details>
            <table>
              <thead>
                <tr>
                  <th>Outcome</th>
                  <th>{p.result.control_strategy}</th>
                  <th>{p.result.treatment_strategy}</th>
                  <th>Difference</th>
                  <th>95% bootstrap CI</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(p.result.metrics).map(([k, m]: any) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>
                      {(m.control_rate_per_exposed_visitor * 100).toFixed(1)}%
                    </td>
                    <td>
                      {(m.treatment_rate_per_exposed_visitor * 100).toFixed(1)}%
                    </td>
                    <td>{(m.difference * 100).toFixed(1)} pp</td>
                    <td>
                      {m.bootstrap_95_ci
                        ? m.bootstrap_95_ci
                            .map((x: number) => (x * 100).toFixed(1) + "%")
                            .join(" – ")
                        : "insufficient visitors"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
    </>
  );
}
function Inspector({ result, close }: { result: Result; close: () => void }) {
  const panel = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    panel.current?.focus();
  }, []);
  return (
    <div
      className="scrim"
      onClick={close}
      onKeyDown={(e) => {
        if (e.key === "Escape") close();
      }}
    >
      <div
        className="inspector"
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="provider-inspector-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="close"
          aria-label="Close provider inspector"
          onClick={close}
        >
          ×
        </button>
        <p className="eyebrow">RANKING INSPECTOR · #{result.rank}</p>
        <h2 id="provider-inspector-title">{result.provider.display_name}</h2>
        <p>{result.provider.headline}</p>
        <div className="big-score">
          {result.score.toFixed(4)}
          <small> MODEL SCORE · NOT A PROBABILITY</small>
        </div>
        <h3>Feature values</h3>
        {Object.entries(result.features).map(([k, v]) => (
          <div className="feature" key={k}>
            <span>{k.replaceAll("_", " ")}</span>
            <b>{Number(v).toFixed(2)}</b>
            <i
              style={{
                width: `${Math.min(100, Math.max(0, Number(v) * 100))}%`,
              }}
            />
          </div>
        ))}
        {Object.keys(result.feature_contributions ?? {}).length > 0 && (
          <>
            <h3>LightGBM score contributions</h3>
            {Object.entries(result.feature_contributions).map(([k, v]) => (
              <div className="contribution" key={k}>
                <span>{k.replaceAll("_", " ")}</span>
                <b className={Number(v) >= 0 ? "positive" : "negative"}>
                  {Number(v) >= 0 ? "+" : ""}
                  {Number(v).toFixed(4)}
                </b>
              </div>
            ))}
          </>
        )}
        <h3>Observed signals</h3>
        {result.explanation.map((x) => (
          <p className="reason" key={x}>
            • {x}
          </p>
        ))}
        <p className="sub">
          Contributions explain the model score for this candidate pool; they do
          not explain user choice or causation.
        </p>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
