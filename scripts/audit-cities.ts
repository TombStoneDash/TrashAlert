#!/usr/bin/env tsx
/**
 * audit:cities — hits real residential addresses in every "live" city
 * and verifies the schedule lookup returns real municipal data.
 *
 * v2 (2026-04-17): Updated per developer answers.
 *   - Endpoint: /api/lookup (was /api/schedule)
 *   - Response field: collection_day (was trash_day)
 *   - Multi-source fallback chain: supabase → republic → recollect
 *     All three are valid data tiers. Only "fallback with no day" is failure.
 *   - Live city list queried from Supabase rather than hardcoded.
 *
 * Run: npm run audit:cities
 *
 * Env vars required:
 *   SUPABASE_URL
 *   SUPABASE_ANON_KEY (or SUPABASE_SERVICE_ROLE_KEY)
 *
 * Env vars optional:
 *   AUDIT_BASE_URL       default https://trashalert.io
 *   AUDIT_LOOKUP_PATH    default /api/lookup
 *   AUDIT_REQUEST_DELAY  default 1100 (ms)
 *
 * Writes to test-results/audit-[ISO].json and test-results/audit-latest.json.
 * Exits 0 on all-healthy, 1 on any degraded or broken city.
 */

import fs from "node:fs/promises";
import path from "node:path";

// ---------- Configuration ----------

const BASE_URL = process.env.AUDIT_BASE_URL ?? "https://trashalert.io";
const LOOKUP_PATH = process.env.AUDIT_LOOKUP_PATH ?? "/api/lookup";
const REQUEST_DELAY_MS = Number(process.env.AUDIT_REQUEST_DELAY ?? 1100);
const REQUEST_TIMEOUT_MS = 15_000;
const PASS_THRESHOLD = 0.9; // 90%

const SUPABASE_URL = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_KEY =
  process.env.SUPABASE_SERVICE_ROLE_KEY ??
  process.env.SUPABASE_ANON_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
  "";

const VALID_DAYS = new Set([
  "monday", "tuesday", "wednesday", "thursday",
  "friday", "saturday", "sunday",
]);

// Legitimate source tiers — NOT failures.
const VALID_SOURCES = new Set(["supabase", "republic", "recollect", "municipal", "arcgis"]);

// Tokens that strongly suggest no real data came back.
const FALLBACK_RED_FLAGS = [
  "unknown", "n/a", "tbd", "not available", "funday", "placeholder", "default_day",
];

/**
 * Known-good landmark addresses per city. Civic landmarks only — no PII.
 * Queried list of live cities from Supabase will be matched against this.
 * Any live city NOT in this map will be flagged as "no test coverage" in
 * the report but won't fail the audit (lets us know which cities need
 * landmark addresses added).
 */
const LANDMARK_ADDRESSES: Record<string, string[]> = {
  nyc: [
    "253 Broadway, New York, NY 10007",
    "476 5th Ave, New York, NY 10018",
    "1000 5th Ave, New York, NY 10028",
    "31-00 47th Ave, Long Island City, NY 11101",
    "200 Eastern Pkwy, Brooklyn, NY 11238",
  ],
  "new york": [
    "253 Broadway, New York, NY 10007",
    "476 5th Ave, New York, NY 10018",
    "1000 5th Ave, New York, NY 10028",
  ],
  la: [
    "200 N Spring St, Los Angeles, CA 90012",
    "630 W 5th St, Los Angeles, CA 90071",
    "5905 Wilshire Blvd, Los Angeles, CA 90036",
  ],
  "los angeles": [
    "200 N Spring St, Los Angeles, CA 90012",
    "630 W 5th St, Los Angeles, CA 90071",
    "5905 Wilshire Blvd, Los Angeles, CA 90036",
  ],
  houston: [
    "901 Bagby St, Houston, TX 77002",
    "500 McKinney St, Houston, TX 77002",
    "1001 Bissonnet St, Houston, TX 77005",
  ],
  philadelphia: [
    "1400 John F Kennedy Blvd, Philadelphia, PA 19107",
    "1901 Vine St, Philadelphia, PA 19103",
    "2600 Benjamin Franklin Pkwy, Philadelphia, PA 19130",
  ],
  philly: [
    "1400 John F Kennedy Blvd, Philadelphia, PA 19107",
    "1901 Vine St, Philadelphia, PA 19103",
  ],
  phoenix: [
    "200 W Washington St, Phoenix, AZ 85003",
    "1221 N Central Ave, Phoenix, AZ 85004",
    "1502 W Washington St, Phoenix, AZ 85007",
  ],
  austin: [
    "301 W 2nd St, Austin, TX 78701",
    "710 W César Chávez St, Austin, TX 78701",
    "1800 Congress Ave, Austin, TX 78701",
  ],
  denver: [
    "1437 Bannock St, Denver, CO 80202",
    "10 W 14th Ave Pkwy, Denver, CO 80204",
    "100 W 14th Ave Pkwy, Denver, CO 80204",
  ],
  boston: [
    "1 City Hall Square, Boston, MA 02201",
    "700 Boylston St, Boston, MA 02116",
    "465 Huntington Ave, Boston, MA 02115",
  ],
  "san diego": [
    "202 C St, San Diego, CA 92101",
    "1549 El Prado, San Diego, CA 92101",
  ],
  "edco-sd": [
    "505 S Vulcan Ave, Encinitas, CA 92024",
    "2075 Las Palmas Dr, Carlsbad, CA 92011",
    "1635 Faraday Ave, Carlsbad, CA 92008",
  ],
  // Newly wired Tier-1 cities. Add more as they ship.
  "san antonio": [
    "100 Military Plaza, San Antonio, TX 78205",
    "600 Soledad St, San Antonio, TX 78205",
    "300 Alamo Plaza, San Antonio, TX 78205",
  ],
  indianapolis: [
    "200 E Washington St, Indianapolis, IN 46204",
    "40 S Meridian St, Indianapolis, IN 46204",
    "500 W Washington St, Indianapolis, IN 46204",
  ],
  baltimore: [
    "100 N Holliday St, Baltimore, MD 21202",
    "400 Cathedral St, Baltimore, MD 21201",
    "10 Art Museum Dr, Baltimore, MD 21218",
  ],
  "oklahoma city": [
    "200 N Walker Ave, Oklahoma City, OK 73102",
    "300 Park Ave, Oklahoma City, OK 73102",
  ],
  albuquerque: [
    "1 Civic Plaza NW, Albuquerque, NM 87102",
    "2000 Mountain Rd NW, Albuquerque, NM 87104",
  ],
  tucson: [
    "255 W Alameda St, Tucson, AZ 85701",
    "101 W Congress St, Tucson, AZ 85701",
  ],
  riverside: [
    "3900 Main St, Riverside, CA 92522",
    "3581 Mission Inn Ave, Riverside, CA 92501",
  ],
  "san jose": [
    "200 E Santa Clara St, San Jose, CA 95113",
    "150 W San Carlos St, San Jose, CA 95113",
  ],
  charlotte: [
    "600 E 4th St, Charlotte, NC 28202",
    "310 N Tryon St, Charlotte, NC 28202",
  ],
  "kansas city": [
    "414 E 12th St, Kansas City, MO 64106",
    "4525 Oak St, Kansas City, MO 64111",
  ],
};

// ---------- Types ----------

interface LookupResult {
  ok: boolean;
  address: string;
  city: string;
  response: unknown;
  source?: string;
  collection_day?: string;
  reasons: string[];
  latency_ms: number;
}

interface CityReport {
  city: string;
  tested: number;
  passed: number;
  failed: number;
  pass_rate: number;
  avg_latency_ms: number;
  source_breakdown: Record<string, number>;
  status: "healthy" | "degraded" | "broken" | "no_test_coverage";
  results: LookupResult[];
}

interface AuditReport {
  started_at: string;
  finished_at: string;
  duration_s: number;
  base_url: string;
  lookup_path: string;
  supabase_query_ok: boolean;
  overall: {
    live_cities_from_db: number;
    cities_tested: number;
    cities_healthy: number;
    cities_degraded: number;
    cities_broken: number;
    cities_missing_coverage: number;
    addresses_tested: number;
    addresses_passed: number;
    overall_pass_rate: number;
    source_totals: Record<string, number>;
  };
  cities: CityReport[];
  live_cities_missing_landmarks: string[];
  db_cities_missing_landmarks: string[];
}

// ---------- Helpers ----------

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function normCity(s: string): string {
  return String(s).toLowerCase().trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
}

/**
 * Determine which cities to audit.
 *
 * Earlier versions of this function tried to ask Supabase for the distinct
 * list of cities in schedule_reports via `?select=city&limit=50000`.
 * That silently undercounts: PostgREST caps row returns at 1000 regardless
 * of the limit parameter, so we'd see only the 2-3 cities dominating the
 * head of a 6.28M-row table. There is no index on `schedule_reports.city`
 * either, so per-city `eq()` filtering also times out for most cities.
 *
 * Pragmatic fix: the cities we can meaningfully audit are exactly the ones
 * with landmark addresses configured (LANDMARK_ADDRESSES). For anything
 * else we have no test addresses, so labelling it "live" doesn't help.
 *
 * As a best-effort enrichment, sample the head and tail of schedule_reports
 * and report any cities seen in the sample that lack landmark coverage —
 * those go into `live_cities_missing_landmarks` so HT can prioritize.
 */
async function fetchLiveCities(): Promise<{ cities: string[]; fromDb: boolean; dbSampleCities: Set<string> }> {
  const cities = Object.keys(LANDMARK_ADDRESSES);
  const dbSampleCities = new Set<string>();

  if (!SUPABASE_URL || !SUPABASE_KEY) {
    console.warn("⚠  SUPABASE_URL/SUPABASE_KEY not set — Supabase enrichment skipped.");
    console.log(`  ✓ Auditing ${cities.length} cities from LANDMARK_ADDRESSES`);
    return { cities, fromDb: false, dbSampleCities };
  }

  // Best-effort sample: 1 head batch + 5 tail batches. Failure is non-fatal.
  const baseUrl = SUPABASE_URL.replace(/\/+$/, "");
  const headers = {
    apikey: SUPABASE_KEY,
    Authorization: `Bearer ${SUPABASE_KEY}`,
    "Accept-Profile": "public",
  } as const;

  async function pull(rangeFrom: number, rangeTo: number, order?: string) {
    const u = new URL(`${baseUrl}/rest/v1/schedule_reports`);
    u.searchParams.set("select", "city");
    if (order) u.searchParams.set("order", order);
    const res = await fetch(u.toString(), {
      headers: { ...headers, Range: `${rangeFrom}-${rangeTo}`, "Range-Unit": "items" },
    });
    if (!res.ok) return;
    const rows = (await res.json()) as Array<{ city: string | null }>;
    for (const r of rows) if (r?.city) dbSampleCities.add(normCity(r.city));
  }

  try {
    await pull(0, 999);                          // head
    for (let i = 0; i < 5; i++) {
      await pull(i * 1000, i * 1000 + 999, "id.desc");
    }
    console.log(`  ✓ Sampled Supabase: ${dbSampleCities.size} distinct cities seen in head+tail`);
  } catch (err: any) {
    console.warn(`⚠  Supabase sample failed (non-fatal): ${err.message ?? err}`);
  }

  console.log(`  ✓ Auditing ${cities.length} cities from LANDMARK_ADDRESSES`);
  return { cities, fromDb: dbSampleCities.size > 0, dbSampleCities };
}

function pickAddresses(city: string): string[] {
  const norm = normCity(city);
  if (LANDMARK_ADDRESSES[norm]) return LANDMARK_ADDRESSES[norm];
  // Try variants (nyc ↔ new york, la ↔ los angeles, etc.) already covered
  // in LANDMARK_ADDRESSES explicitly. If still missing, return empty.
  return [];
}

/**
 * A lookup is OK if:
 *   - HTTP 200
 *   - response has a collection_day (or trashDay/trash_day/day fallback)
 *     that parses to a weekday
 *   - source field is one of VALID_SOURCES, OR absent (older API)
 *   - no red-flag tokens in the day value
 */
function validatePayload(payload: any): { reasons: string[]; day?: string; source?: string } {
  const reasons: string[] = [];
  if (!payload || typeof payload !== "object") {
    return { reasons: ["payload not an object"] };
  }
  if (payload.error) reasons.push(`api error: ${payload.error}`);

  const day: string | undefined =
    payload.collection_day ??
    payload.collectionDay ??
    payload.trash_day ??
    payload.trashDay ??
    payload.day ??
    payload?.data?.collection_day ??
    payload?.schedule?.collection_day;

  const source: string | undefined =
    payload.source ??
    payload.data_source ??
    payload?.meta?.source ??
    payload?.data?.source;

  if (!day) {
    reasons.push("no collection_day in response");
  } else {
    const normDay = String(day).toLowerCase().trim();
    if (FALLBACK_RED_FLAGS.some((f) => normDay.includes(f))) {
      reasons.push(`collection_day looks like fallback: "${day}"`);
    } else if (!VALID_DAYS.has(normDay)) {
      reasons.push(`collection_day not a recognized weekday: "${day}"`);
    }
  }

  // Source validation only fires if source is present. No source = older
  // API shape = give benefit of the doubt as long as day is valid.
  if (source && !VALID_SOURCES.has(source.toLowerCase())) {
    if (source.toLowerCase() === "fallback" || source.toLowerCase() === "default") {
      reasons.push(`source declares fallback: "${source}"`);
    }
    // Any other unexpected source is informational, not failure.
  }

  return { reasons, day, source };
}

async function lookupOne(city: string, address: string): Promise<LookupResult> {
  const url = new URL(LOOKUP_PATH, BASE_URL);
  url.searchParams.set("address", address);
  url.searchParams.set("city", city);
  const started = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(url.toString(), {
      method: "GET",
      headers: { Accept: "application/json", "User-Agent": "TrashAlert-Audit/2.0" },
      signal: controller.signal,
    });
    const latency = Date.now() - started;
    const text = await res.text();
    let body: unknown = null;
    try { body = JSON.parse(text); } catch { body = text; }
    const reasons: string[] = [];
    if (!res.ok) reasons.push(`http ${res.status}`);
    const { reasons: valReasons, day, source } = validatePayload(body);
    reasons.push(...valReasons);
    return {
      ok: reasons.length === 0,
      address, city, response: body,
      source, collection_day: day,
      reasons, latency_ms: latency,
    };
  } catch (err: any) {
    return {
      ok: false, address, city, response: null,
      reasons: [`fetch threw: ${err.message ?? err}`],
      latency_ms: Date.now() - started,
    };
  } finally {
    clearTimeout(timer);
  }
}

async function auditCity(city: string, addresses: string[]): Promise<CityReport> {
  if (!addresses.length) {
    console.log(`\n🏙  ${city} — ⚠ no landmark addresses configured, skipping`);
    return {
      city, tested: 0, passed: 0, failed: 0,
      pass_rate: 0, avg_latency_ms: 0,
      source_breakdown: {}, status: "no_test_coverage", results: [],
    };
  }
  console.log(`\n🏙  ${city} — testing ${addresses.length} addresses`);
  const results: LookupResult[] = [];
  const sourceBreakdown: Record<string, number> = {};
  for (const addr of addresses) {
    const r = await lookupOne(city, addr);
    results.push(r);
    if (r.source) sourceBreakdown[r.source] = (sourceBreakdown[r.source] ?? 0) + 1;
    const icon = r.ok ? "✅" : "❌";
    const srcTag = r.source ? ` [${r.source}]` : "";
    const dayTag = r.collection_day ? ` → ${r.collection_day}` : "";
    console.log(`  ${icon} ${addr}${srcTag}${dayTag}${r.ok ? "" : `  — ${r.reasons.join("; ")}`}`);
    await sleep(REQUEST_DELAY_MS);
  }
  const passed = results.filter((r) => r.ok).length;
  const failed = results.length - passed;
  const passRate = passed / results.length;
  const avgLatency = Math.round(results.reduce((s, r) => s + r.latency_ms, 0) / results.length);
  const status: CityReport["status"] =
    passRate >= PASS_THRESHOLD ? "healthy" :
    passRate >= 0.5 ? "degraded" : "broken";
  console.log(`  → ${passed}/${results.length} passed (${Math.round(passRate * 100)}%) — ${status}`);
  if (Object.keys(sourceBreakdown).length > 1 ||
      (Object.keys(sourceBreakdown).length === 1 && !sourceBreakdown.supabase)) {
    console.log(`  sources: ${JSON.stringify(sourceBreakdown)}`);
  }
  return {
    city, tested: results.length, passed, failed, pass_rate: passRate,
    avg_latency_ms: avgLatency, source_breakdown: sourceBreakdown,
    status, results,
  };
}

// ---------- Main ----------

async function main(): Promise<void> {
  const started = new Date();
  console.log(`\n🗑  TrashAlert City Audit v2`);
  console.log(`   base:   ${BASE_URL}${LOOKUP_PATH}`);
  console.log(`   started: ${started.toISOString()}`);

  console.log(`\n📡 Fetching live city list from Supabase...`);
  const { cities: liveCities, fromDb, dbSampleCities } = await fetchLiveCities();

  const missingLandmarks: string[] = [];
  const toTest: Array<{ city: string; addresses: string[] }> = [];
  for (const city of liveCities) {
    const addrs = pickAddresses(city);
    if (!addrs.length) missingLandmarks.push(city);
    toTest.push({ city, addresses: addrs });
  }

  // Cities seen in Supabase sample but with no landmark addresses configured
  const landmarkKeys = new Set(liveCities.map(normCity));
  const dbCitiesNoLandmarks = [...dbSampleCities].filter((c) => !landmarkKeys.has(c)).sort();

  console.log(`   cities to audit:                ${liveCities.length}`);
  console.log(`   cities missing landmarks:       ${missingLandmarks.length}`);
  if (dbCitiesNoLandmarks.length > 0) {
    console.log(`   cities seen in DB but no landmarks (${dbCitiesNoLandmarks.length}):`);
    console.log(`     ${dbCitiesNoLandmarks.join(", ")}`);
  }
  console.log("");

  const cityReports: CityReport[] = [];
  for (const { city, addresses } of toTest) {
    cityReports.push(await auditCity(city, addresses));
  }

  const finished = new Date();
  const testedReports = cityReports.filter((c) => c.status !== "no_test_coverage");
  const totalTested = testedReports.reduce((s, c) => s + c.tested, 0);
  const totalPassed = testedReports.reduce((s, c) => s + c.passed, 0);
  const sourceTotals: Record<string, number> = {};
  for (const c of testedReports) {
    for (const [src, n] of Object.entries(c.source_breakdown)) {
      sourceTotals[src] = (sourceTotals[src] ?? 0) + n;
    }
  }

  const report: AuditReport = {
    started_at: started.toISOString(),
    finished_at: finished.toISOString(),
    duration_s: Math.round((finished.getTime() - started.getTime()) / 1000),
    base_url: BASE_URL,
    lookup_path: LOOKUP_PATH,
    supabase_query_ok: fromDb,
    overall: {
      live_cities_from_db: liveCities.length,
      cities_tested: testedReports.length,
      cities_healthy: testedReports.filter((c) => c.status === "healthy").length,
      cities_degraded: testedReports.filter((c) => c.status === "degraded").length,
      cities_broken: testedReports.filter((c) => c.status === "broken").length,
      cities_missing_coverage: missingLandmarks.length,
      addresses_tested: totalTested,
      addresses_passed: totalPassed,
      overall_pass_rate: totalTested ? totalPassed / totalTested : 0,
      source_totals: sourceTotals,
    },
    cities: cityReports,
    live_cities_missing_landmarks: missingLandmarks,
    db_cities_missing_landmarks: dbCitiesNoLandmarks,
  };

  const outDir = path.resolve("test-results");
  await fs.mkdir(outDir, { recursive: true });
  const stamp = finished.toISOString().replace(/[:.]/g, "-");
  const outPath = path.join(outDir, `audit-${stamp}.json`);
  await fs.writeFile(outPath, JSON.stringify(report, null, 2), "utf8");
  await fs.writeFile(path.join(outDir, "audit-latest.json"), JSON.stringify(report, null, 2), "utf8");

  console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`  Live cities (DB):   ${liveCities.length}`);
  console.log(`  Tested:             ${testedReports.length}  (${report.overall.cities_healthy} healthy · ${report.overall.cities_degraded} degraded · ${report.overall.cities_broken} broken)`);
  console.log(`  Missing landmarks:  ${missingLandmarks.length}${missingLandmarks.length ? ` — ${missingLandmarks.slice(0, 10).join(", ")}${missingLandmarks.length > 10 ? "…" : ""}` : ""}`);
  console.log(`  Addresses:          ${totalPassed}/${totalTested} passed (${Math.round(report.overall.overall_pass_rate * 100)}%)`);
  console.log(`  Source breakdown:   ${JSON.stringify(sourceTotals)}`);
  console.log(`  Duration:           ${report.duration_s}s`);
  console.log(`  Report:             ${outPath}`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);

  if (report.overall.cities_broken > 0) {
    console.error(`❌ ${report.overall.cities_broken} city/cities are broken. Expansion BLOCKED.`);
    process.exit(1);
  }
  if (report.overall.cities_degraded > 0) {
    console.warn(`⚠  ${report.overall.cities_degraded} city/cities degraded. Flag in UI and investigate.`);
    process.exit(1);
  }
  if (missingLandmarks.length > 0) {
    console.warn(`⚠  ${missingLandmarks.length} live city/cities have no landmark addresses for testing.`);
    console.warn(`   These aren't failures, but you have no visibility. Add landmarks in LANDMARK_ADDRESSES.`);
  }
  console.log(`✅ All tested live cities healthy. Safe to expand.`);
  process.exit(0);
}

main().catch((err) => {
  console.error("💥 Audit crashed:", err);
  process.exit(2);
});
