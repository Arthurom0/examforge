import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Agg, api, CourseStats } from "../api";
import { Card, Empty, inputCls, pct, Spinner, useLoad } from "../components/ui";

const SERIES = Array.from({ length: 8 }, (_, i) => `var(--series-${i + 1})`);
const ORIGIN_COLOR = { generated: "var(--series-1)", booklet: "var(--series-2)" };

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </Card>
  );
}

/** Horizontal rate bar with a direct value label; empty track when there is no data. */
function RateBar({ agg, color, label }: { agg: Agg; color: string; label: string }) {
  const rate = agg.success_rate;
  return (
    <div className="group flex items-center gap-2 text-xs" title={`${label}: ${pct(rate)} over ${agg.attempts} attempt(s) · ${agg.correct} correct, ${agg.partial} partial, ${agg.wrong} wrong`}>
      <span className="w-16 shrink-0 text-slate-500">{label}</span>
      <div className="h-2.5 flex-1 rounded-full bg-slate-100 dark:bg-slate-800">
        {rate !== null && (
          <div className="h-2.5 rounded-full transition-all" style={{ width: `${Math.max(rate * 100, 2)}%`, background: color }} />
        )}
      </div>
      <span className="w-20 shrink-0 text-right tabular-nums text-slate-700 dark:text-slate-300">
        {rate === null ? "no data" : `${pct(rate)} · ${agg.attempts}`}
      </span>
    </div>
  );
}

function CourseCard({ c }: { c: CourseStats }) {
  return (
    <Card>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-semibold">{c.name}</h3>
        <span className="text-sm tabular-nums text-slate-500">
          {pct(c.success_rate)} · {c.attempts} attempts
        </span>
      </div>
      <div className="mb-4 space-y-1.5">
        <RateBar agg={c.generated} color={ORIGIN_COLOR.generated} label="Generated" />
        <RateBar agg={c.booklet} color={ORIGIN_COLOR.booklet} label="Booklet" />
      </div>
      <div className="space-y-3">
        {c.chapters.map((ch) => (
          <div key={ch.chapter_id ?? "none"}>
            <div className="mb-1 flex justify-between text-sm">
              <span>{ch.name}</span>
              <span className="tabular-nums text-slate-500">{pct(ch.success_rate)}</span>
            </div>
            <div className="space-y-1 pl-2">
              <RateBar agg={ch.generated} color={ORIGIN_COLOR.generated} label="Generated" />
              <RateBar agg={ch.booklet} color={ORIGIN_COLOR.booklet} label="Booklet" />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function Dashboard() {
  const overview = useLoad(api.overview, []);
  const [courseId, setCourseId] = useState<number | undefined>();
  const [origin, setOrigin] = useState<string>("");
  const [granularity, setGranularity] = useState("week");
  const timeline = useLoad(() => api.timeline({ course_id: courseId, origin: origin || undefined, granularity }), [courseId, origin, granularity]);
  const topics = useLoad(() => (courseId ? api.topics(courseId, origin || undefined) : Promise.resolve([])), [courseId, origin]);

  if (overview.loading && !overview.data) return <Spinner />;
  const data = overview.data ?? [];
  const total = data.reduce((s, c) => s + c.attempts, 0);
  if (!total)
    return (
      <Empty>
        No attempts yet. Mark problems and booklet exercises as correct, partial or wrong while practicing, and your progress shows up here.
      </Empty>
    );

  const weighted = (key: "generated" | "booklet" | null) => {
    let n = 0,
      s = 0;
    for (const c of data) {
      const a = key ? c[key] : c;
      if (a.success_rate !== null) {
        n += a.attempts;
        s += a.success_rate * a.attempts;
      }
    }
    return { rate: n ? s / n : null, n };
  };
  const all = weighted(null);
  const gen = weighted("generated");
  const bk = weighted("booklet");

  // Recharts wants one row per period with a column per series.
  const tl = timeline.data;
  const seriesList = (tl?.series ?? []).filter((s) => s.key !== "all" || (tl?.series.length ?? 0) <= 2).sort((a, b) => a.key.localeCompare(b.key));
  const showSeries = seriesList.length > 1 ? seriesList.filter((s) => s.key !== "all") : seriesList;
  const rows = (tl?.periods ?? []).map((p) => {
    const row: Record<string, string | number | null> = { period: p };
    for (const s of showSeries) {
      const pt = s.points.find((x) => x.period === p);
      row[s.key] = pt ? Math.round(pt.success_rate * 100) : null;
      row[`${s.key}__n`] = pt?.attempts ?? 0;
    }
    return row;
  });
  // Color follows the entity: stable index by key across filters.
  const colorFor = (key: string) => {
    const keys = (tl?.series ?? []).map((s) => s.key).filter((k) => k !== "all").sort();
    const i = keys.indexOf(key);
    return key === "all" ? SERIES[0] : SERIES[(i >= 0 ? i : 0) % SERIES.length];
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid gap-3 sm:grid-cols-3">
        <Tile label="Overall success" value={pct(all.rate)} sub={`${all.n} attempts`} />
        <Tile label="Generated problems" value={pct(gen.rate)} sub={`${gen.n} attempts`} />
        <Tile label="Booklet exercises" value={pct(bk.rate)} sub={`${bk.n} attempts`} />
      </div>
      <p className="-mt-3 text-xs text-slate-500">Success rate counts correct as 1, partial as ½ and wrong as 0.</p>

      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <h2 className="mr-auto font-semibold">Success rate over time</h2>
          <select className={`${inputCls} !w-52`} value={courseId ?? ""} onChange={(e) => setCourseId(e.target.value ? Number(e.target.value) : undefined)}>
            <option value="">All courses (one line each)</option>
            {data.map((c) => (
              <option key={c.course_id} value={c.course_id}>
                {c.name} (by chapter)
              </option>
            ))}
          </select>
          <select className={`${inputCls} !w-40`} value={origin} onChange={(e) => setOrigin(e.target.value)}>
            <option value="">All problems</option>
            <option value="generated">Generated only</option>
            <option value="booklet">Booklet only</option>
          </select>
          <select className={`${inputCls} !w-28`} value={granularity} onChange={(e) => setGranularity(e.target.value)}>
            <option value="week">Weekly</option>
            <option value="day">Daily</option>
          </select>
        </div>
        {!rows.length ? (
          <p className="py-10 text-center text-sm text-slate-500">No attempts for this selection.</p>
        ) : (
          <div className="h-72">
            <ResponsiveContainer>
              <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="period" tick={{ fill: "var(--axis)", fontSize: 12 }} tickLine={false} axisLine={{ stroke: "var(--grid)" }} />
                <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} unit=" %" tick={{ fill: "var(--axis)", fontSize: 12 }} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ stroke: "var(--axis)", strokeDasharray: "3 3" }}
                  contentStyle={{ borderRadius: 8, fontSize: 12, background: "var(--surface)", borderColor: "var(--grid)" }}
                  formatter={(v, name, item) => {
                    const key = String(item.dataKey);
                    const n = (item.payload as Record<string, number>)[`${key}__n`];
                    return [`${v} % (${n} attempts)`, name];
                  }}
                />
                {showSeries.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
                {showSeries.map((s) => (
                  <Line
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    name={s.name}
                    stroke={colorFor(s.key)}
                    strokeWidth={2}
                    dot={{ r: 4, strokeWidth: 2, fill: "var(--surface)" }}
                    activeDot={{ r: 5 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {courseId && (
        <Card>
          <h2 className="mb-1 font-semibold">Topics, weakest first</h2>
          <p className="mb-3 text-xs text-slate-500">Weak-spot mode targets the top of this list. Ranking uses a smoothed rate so one bad attempt does not dominate.</p>
          {!topics.data?.length ? (
            <p className="text-sm text-slate-500">No tagged attempts yet. Tag booklet exercises with topics (or use Auto-tag) to track them here.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="py-1">Topic</th>
                  <th className="w-1/2">Success rate</th>
                  <th className="text-right">Attempts</th>
                </tr>
              </thead>
              <tbody>
                {topics.data.map((t) => (
                  <tr key={t.topic} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="py-1.5">{t.topic}</td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="h-2 flex-1 rounded-full bg-slate-100 dark:bg-slate-800">
                          <div className="h-2 rounded-full" style={{ width: `${Math.max(t.success_rate * 100, 2)}%`, background: "var(--series-1)" }} />
                        </div>
                        <span className="w-12 text-right tabular-nums">{pct(t.success_rate)}</span>
                      </div>
                    </td>
                    <td className="text-right tabular-nums">{t.attempts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      <div>
        <h2 className="mb-3 font-semibold">By course and chapter</h2>
        <div className="mb-3 flex gap-4 text-xs text-slate-600 dark:text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: ORIGIN_COLOR.generated }} /> Generated problems
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: ORIGIN_COLOR.booklet }} /> Original booklet exercises
          </span>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((c) => (
            <CourseCard key={c.course_id} c={c} />
          ))}
        </div>
      </div>
    </div>
  );
}
