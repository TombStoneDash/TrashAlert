// scripts/diag-supabase-cities.ts
// Reports actual city distribution in schedule_reports.
// Strategy: table has ~6.28M rows. eq(city, …) count() times out (no index).
// Instead, take a stratified sample of 10 × 1000 rows from offsets across
// the table and report city distribution. Extrapolate to full row count.
// Run: npx tsx --env-file=.env.local scripts/diag-supabase-cities.ts
import { createClient } from "@supabase/supabase-js";

const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL!;
const key =
  process.env.SUPABASE_SERVICE_KEY ??
  process.env.SUPABASE_SERVICE_ROLE_KEY ??
  process.env.SUPABASE_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

if (!url || !key) {
  console.error("Missing SUPABASE_URL or key.");
  process.exit(2);
}

console.log(`Connecting to: ${url}`);
console.log(`Key length:    ${key.length} chars (prefix ${key.slice(0, 12)}…)\n`);

const sb = createClient(url, key);

async function main() {
  // 1) Get total row count (estimated, fast)
  const { count: total, error: countErr } = await sb
    .from("schedule_reports")
    .select("*", { count: "estimated", head: true });
  if (countErr) {
    console.error("count error:", countErr);
    process.exit(1);
  }
  console.log(`schedule_reports total rows (estimated): ~${total?.toLocaleString()}\n`);

  // 2) Stratified sample: 10 batches of 1000 from offsets evenly spaced across the table
  const BATCHES = 10;
  const BATCH_SIZE = 1000;
  const totalRows = total ?? 6_000_000;
  const stride = Math.max(1, Math.floor((totalRows - BATCH_SIZE) / BATCHES));

  const counts = new Map<string, number>();
  let sampleSize = 0;
  console.log(`Sampling ${BATCHES} batches of ${BATCH_SIZE} rows (stride ${stride.toLocaleString()})...\n`);

  for (let i = 0; i < BATCHES; i++) {
    const offset = i * stride;
    const { data, error } = await sb
      .from("schedule_reports")
      .select("city")
      .range(offset, offset + BATCH_SIZE - 1);
    if (error) {
      console.error(`batch ${i} (offset ${offset}) error:`, error.message || error);
      continue;
    }
    if (!data || data.length === 0) {
      console.error(`batch ${i} (offset ${offset}) — no data`);
      continue;
    }
    for (const row of data) {
      const c = (row.city ?? "(null)").toString().toLowerCase().trim();
      counts.set(c, (counts.get(c) ?? 0) + 1);
    }
    sampleSize += data.length;
    process.stdout.write(`  batch ${i + 1}/${BATCHES} (offset ${offset.toLocaleString()}) — ${data.length} rows · running cities: ${counts.size}\n`);
  }

  console.log(`\n=== Sample distribution (${sampleSize} rows sampled of ~${total?.toLocaleString()}) ===`);
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  for (const [city, n] of sorted) {
    const pct = ((n / sampleSize) * 100).toFixed(1);
    const extrapolated = Math.round((n / sampleSize) * (total ?? 0));
    console.log(`  ${city.padEnd(28)} ${n.toString().padStart(5)} (${pct.padStart(5)}%) → est. ${extrapolated.toLocaleString()} rows total`);
  }

  // 3) Pull the tail too (latest inserted rows) — may reveal recent imports
  console.log(`\nSampling tail of table (5000 latest by id)...`);
  const tailCounts = new Map<string, number>();
  for (let i = 0; i < 5; i++) {
    const { data, error } = await sb
      .from("schedule_reports")
      .select("city")
      .order("id", { ascending: false })
      .range(i * 1000, i * 1000 + 999);
    if (error) {
      console.error(`  tail batch ${i} error:`, error.message || error);
      break;
    }
    if (!data || data.length === 0) break;
    for (const row of data) {
      const c = (row.city ?? "(null)").toString().toLowerCase().trim();
      tailCounts.set(c, (tailCounts.get(c) ?? 0) + 1);
    }
    process.stdout.write(`  tail batch ${i + 1}/5 — ${data.length} rows · cities seen: ${tailCounts.size}\n`);
  }
  console.log(`\n=== Tail distribution (latest 5000 rows by id desc) ===`);
  for (const [city, n] of [...tailCounts.entries()].sort((a, b) => b[1] - a[1])) {
    console.log(`  ${city.padEnd(28)} ${n}`);
  }

  // Merge for final union
  const union = new Map<string, number>(counts);
  for (const [c, n] of tailCounts) union.set(c, (union.get(c) ?? 0) + n);

  console.log(`\n=== Summary ===`);
  console.log(`  Distinct cities (head sample):  ${counts.size}`);
  console.log(`  Distinct cities (tail sample):  ${tailCounts.size}`);
  console.log(`  Distinct cities (union):        ${union.size}`);
  console.log(`  Cities seen anywhere:           ${[...union.keys()].sort().join(", ")}`);
  console.log(`  Total schedule_reports rows:    ~${total?.toLocaleString()}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
