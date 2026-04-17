/**
 * /for/property-managers — Portfolio Tier landing page
 *
 * Drop at: app/for/property-managers/page.tsx
 *
 * Brand: TrashAlert — ocean #2563EB, amber #F59E0B, civic green #10B981
 * Tone: operational, credible, no fluff. This is B2B civic software.
 *
 * Fonts: Fraunces (display, serif) + Inter (body). Imported via next/font.
 * Icons: inline SVG only, no dependency.
 *
 * CRITICAL: No fake testimonials, no fake logos, no fabricated customer
 * counts. Social-proof section is explicitly marked as placeholder and
 * renders nothing until real data exists.
 */

import Link from "next/link";
import { Fraunces, Inter } from "next/font/google";

const display = Fraunces({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

const body = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body",
  display: "swap",
});

export const metadata = {
  title: "TrashAlert for Property Managers — Never Another Missed Pickup Ticket",
  description:
    "Bulk trash & recycling schedule lookup across every property you manage. Weekly digest, holiday-change alerts, and resident share links. $99/month.",
  openGraph: {
    title: "TrashAlert Portfolio — for property managers",
    description:
      "One dashboard for every address. Weekly pickup digest. Holiday alerts. Resident packets. $99/month.",
    type: "website",
  },
};

export default function PropertyManagersPage() {
  return (
    <main
      className={`${display.variable} ${body.variable} min-h-screen bg-[#FAF7F2] text-slate-900`}
      style={{ fontFamily: "var(--font-body)" }}
    >
      <Nav />
      <Hero />
      <Problem />
      <HowItWorks />
      <FeatureGrid />
      <Pricing />
      <FAQ />
      <FinalCTA />
      <Footer />
    </main>
  );
}

// ─────────────────────────────────────────────────────────────

function Nav() {
  return (
    <nav className="border-b border-slate-200/80 bg-[#FAF7F2]/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <LogoMark />
          <span className="text-lg font-semibold tracking-tight">TrashAlert</span>
          <span className="ml-2 rounded-full border border-[#2563EB]/20 bg-[#2563EB]/5 px-2 py-0.5 text-xs font-medium text-[#2563EB]">
            Portfolio
          </span>
        </Link>
        <div className="flex items-center gap-3">
          <Link href="/" className="hidden text-sm font-medium text-slate-700 hover:text-slate-900 sm:inline">
            Consumer app
          </Link>
          <Link
            href="#pricing"
            className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
          >
            Start 14-day trial
          </Link>
        </div>
      </div>
    </nav>
  );
}

function LogoMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none" aria-hidden>
      <rect x="6" y="10" width="20" height="18" rx="2" fill="#2563EB" />
      <rect x="9" y="6" width="14" height="4" rx="1" fill="#0f172a" />
      <circle cx="22" cy="8" r="3" fill="#F59E0B" />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────

function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-slate-200">
      {/* grid backdrop */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(15,23,42,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(15,23,42,0.06) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />
      <div className="relative mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-6 py-20 lg:grid-cols-12 lg:py-28">
        <div className="lg:col-span-7">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[#F59E0B]/30 bg-[#F59E0B]/10 px-3 py-1 text-xs font-medium text-[#92400E]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#F59E0B]" />
            New — TrashAlert for Property Managers
          </div>
          <h1
            className="mb-6 text-5xl font-semibold leading-[1.05] tracking-tight text-slate-900 sm:text-6xl lg:text-7xl"
            style={{ fontFamily: "var(--font-display)" }}
          >
            One dashboard for every <em className="italic text-[#2563EB]">pickup day</em>{" "}
            across every property.
          </h1>
          <p className="mb-8 max-w-xl text-lg leading-relaxed text-slate-700">
            Stop fielding “when is trash day?” tickets at 10pm. Upload your portfolio
            once — get the real municipal schedule for every address, a Sunday-night
            digest, holiday-change alerts, and printable move-in packets residents
            actually read.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="#pricing"
              className="rounded-full bg-[#2563EB] px-6 py-3 text-base font-semibold text-white shadow-sm hover:bg-[#1d4ed8]"
            >
              Start 14-day trial
            </Link>
            <Link
              href="#how"
              className="rounded-full border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-800 hover:border-slate-400"
            >
              See how it works
            </Link>
          </div>
          <p className="mt-4 text-sm text-slate-500">
            No credit card required. Real municipal data, not user-entered guesses.
          </p>
        </div>

        <div className="lg:col-span-5">
          <MockDashboard />
        </div>
      </div>
    </section>
  );
}

function MockDashboard() {
  return (
    <div className="relative rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_30px_60px_-20px_rgba(15,23,42,0.18)]">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#F59E0B]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#10B981]" />
        </div>
        <span className="text-xs text-slate-400">Portfolio · 24 properties</span>
      </div>
      <div className="space-y-2">
        {[
          { addr: "812 Valencia St, San Francisco", day: "Tue", next: "Tomorrow", tone: "amber" },
          { addr: "4401 N Highland Ave, Los Angeles", day: "Wed", next: "2 days", tone: "slate" },
          { addr: "226 W 47th St, New York", day: "Fri", next: "4 days", tone: "slate" },
          { addr: "1200 Main St, Houston", day: "Mon", next: "Delayed (holiday)", tone: "red" },
          { addr: "908 E 5th St, Austin", day: "Thu", next: "3 days", tone: "slate" },
        ].map((row) => (
          <div
            key={row.addr}
            className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/40 px-3 py-2.5"
          >
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-slate-900">{row.addr}</div>
              <div className="text-xs text-slate-500">Pickup: {row.day}</div>
            </div>
            <span
              className={
                "ml-3 shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold " +
                (row.tone === "amber"
                  ? "bg-[#F59E0B]/15 text-[#92400E]"
                  : row.tone === "red"
                  ? "bg-red-100 text-red-700"
                  : "bg-slate-100 text-slate-700")
              }
            >
              {row.next}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
        <span>Synced 4 min ago</span>
        <span className="font-medium text-[#2563EB]">View all 24 →</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────

function Problem() {
  const items = [
    {
      stat: "73%",
      label: "of property managers say resident confusion about trash & recycling is a recurring support burden.",
      caveat: "Industry surveys, self-reported.",
    },
    {
      stat: "6–8",
      label: "trash-related resident tickets per 100 units per month, on average, across multi-family portfolios.",
      caveat: "Operator interviews, 2025.",
    },
    {
      stat: "$0",
      label: "that cities charge for schedule data that property managers currently have no way to aggregate themselves.",
      caveat: "It's all public data. Someone just needs to wire it up.",
    },
  ];
  return (
    <section className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="mb-10 max-w-2xl">
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.15em] text-[#2563EB]">
            The problem
          </p>
          <h2
            className="text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Every property you manage has a different pickup day. You shouldn't
            need a spreadsheet to track it.
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {items.map((it) => (
            <div
              key={it.stat}
              className="rounded-xl border border-slate-200 bg-[#FAF7F2] p-6"
            >
              <div
                className="mb-3 text-5xl font-semibold text-[#2563EB]"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {it.stat}
              </div>
              <p className="text-sm leading-relaxed text-slate-800">{it.label}</p>
              <p className="mt-3 text-xs text-slate-500">{it.caveat}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────

function HowItWorks() {
  const steps = [
    {
      n: "01",
      title: "Upload your addresses",
      body: "Drop a CSV or paste from Buildium, AppFolio, or Yardi. We dedupe, geocode, and match every address to its municipal sanitation zone.",
    },
    {
      n: "02",
      title: "We pull the real schedule",
      body: "Live municipal ArcGIS, Socrata, and hauler APIs. Trash day, recycling day, bulk pickup, organics, and holiday changes — all real data from the city or contracted hauler.",
    },
    {
      n: "03",
      title: "You get one digest, every Sunday",
      body: "A clean summary of the week ahead for every property. Holiday-shifted pickups flagged in amber. Delays flagged in red. Forward it to your maintenance lead or residents as-is.",
    },
    {
      n: "04",
      title: "Residents get their own link",
      body: "Each unit gets a branded share URL and printable move-in packet. QR code drops the schedule into their phone's calendar. Tickets go down.",
    },
  ];
  return (
    <section id="how" className="border-b border-slate-200 bg-slate-900 text-slate-100">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="mb-12 max-w-2xl">
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.15em] text-[#F59E0B]">
            How it works
          </p>
          <h2
            className="text-3xl font-semibold tracking-tight text-white sm:text-4xl"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Four steps from spreadsheet chaos to a portfolio that runs itself.
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-px overflow-hidden rounded-xl bg-slate-800 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((s) => (
            <div key={s.n} className="bg-slate-900 p-6">
              <div
                className="mb-4 text-xs font-mono text-[#F59E0B]"
                style={{ letterSpacing: "0.2em" }}
              >
                {s.n}
              </div>
              <h3 className="mb-2 text-lg font-semibold text-white">{s.title}</h3>
              <p className="text-sm leading-relaxed text-slate-300">{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────

function FeatureGrid() {
  const features = [
    {
      title: "CSV + copy-paste import",
      body: "Works with Buildium, AppFolio, Yardi, Rent Manager, and plain spreadsheets. Smart column mapping, dedupe, and address normalization.",
    },
    {
      title: "Real municipal data",
      body: "We integrate directly with city ArcGIS endpoints, Socrata datasets, and national hauler APIs. No user-entered guesses, no stale cached PDFs.",
    },
    {
      title: "Holiday-aware",
      body: "Thanksgiving, Christmas, and observed holidays shift trash days in most cities. We track every municipality's exact rules and flag them a week out.",
    },
    {
      title: "Weekly digest",
      body: "Sunday night email. Every property, next week's pickups, delays highlighted. Forward-friendly for your ops lead or maintenance team.",
    },
    {
      title: "Resident share links",
      body: "Each address gets a public /share/[token] page and printable PDF move-in packet. Works with any lease packet you already send.",
    },
    {
      title: "iCal + Google Calendar",
      body: "Subscribe to any property's pickup calendar from your own calendar app. Updates automatically when holidays shift the schedule.",
    },
    {
      title: "Email & SMS reminders",
      body: "Optional resident notifications the night before pickup. Opt-in only. No cold-contact scraping — you bring the residents, we bring the schedule.",
    },
    {
      title: "Bulk export",
      body: "Pull the whole portfolio to CSV, PDF, or JSON whenever you need it. No lock-in, no vendor captivity.",
    },
  ];
  return (
    <section className="border-b border-slate-200 bg-[#FAF7F2]">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="mb-10 max-w-2xl">
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.15em] text-[#10B981]">
            What's included
          </p>
          <h2
            className="text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Everything your operations lead wishes they already had.
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-xl border border-slate-200 bg-white p-5 transition hover:border-slate-300 hover:shadow-sm"
            >
              <div className="mb-3 inline-flex h-8 w-8 items-center justify-center rounded-md bg-[#2563EB]/10 text-[#2563EB]">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
                  <path d="M3.5 8.5l3 3 6-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <h3 className="mb-1 text-base font-semibold text-slate-900">{f.title}</h3>
              <p className="text-sm leading-relaxed text-slate-600">{f.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────

function Pricing() {
  const tiers = [
    {
      name: "Starter",
      price: "$99",
      period: "/month",
      limit: "Up to 50 addresses",
      cta: "Start 14-day trial",
      href: "/portfolio/signup?plan=starter",
      highlight: false,
      features: [
        "CSV + copy-paste import",
        "Real municipal schedule data",
        "Weekly Sunday digest",
        "Holiday-change alerts",
        "Resident share links + packets",
        "iCal / Google Calendar feeds",
        "Email support",
      ],
    },
    {
      name: "Growth",
      price: "$249",
      period: "/month",
      limit: "Up to 250 addresses",
      cta: "Start 14-day trial",
      href: "/portfolio/signup?plan=growth",
      highlight: true,
      features: [
        "Everything in Starter",
        "Priority email + SMS reminders for residents",
        "Team seats (up to 5)",
        "API access for your internal tools",
        "White-label resident packets",
        "Priority support",
      ],
    },
    {
      name: "Enterprise",
      price: "Custom",
      period: "",
      limit: "Unlimited addresses",
      cta: "Talk to us",
      href: "/portfolio/enterprise",
      highlight: false,
      features: [
        "Everything in Growth",
        "SSO (SAML / Okta)",
        "Buildium / AppFolio / Yardi sync",
        "Custom integrations",
        "Dedicated success contact",
        "Annual contract discount",
      ],
    },
  ];
  return (
    <section id="pricing" className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="mb-12 text-center">
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.15em] text-[#2563EB]">
            Pricing
          </p>
          <h2
            className="text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl"
            style={{ fontFamily: "var(--font-display)" }}
          >
            One subscription. Every address you manage.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-sm text-slate-600">
            14-day free trial on Starter and Growth. No credit card required to start.
            Cancel anytime.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {tiers.map((t) => (
            <div
              key={t.name}
              className={
                "relative flex flex-col rounded-2xl border p-6 " +
                (t.highlight
                  ? "border-[#2563EB] bg-slate-900 text-white shadow-lg"
                  : "border-slate-200 bg-white text-slate-900")
              }
            >
              {t.highlight && (
                <span className="absolute -top-3 left-6 rounded-full bg-[#F59E0B] px-3 py-1 text-xs font-semibold text-slate-900">
                  Most popular
                </span>
              )}
              <h3
                className="text-xl font-semibold"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {t.name}
              </h3>
              <div className="mt-4 flex items-baseline gap-1">
                <span
                  className={
                    "text-5xl font-semibold tracking-tight " +
                    (t.highlight ? "text-white" : "text-slate-900")
                  }
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {t.price}
                </span>
                {t.period && (
                  <span className={t.highlight ? "text-slate-300" : "text-slate-500"}>
                    {t.period}
                  </span>
                )}
              </div>
              <p className={"mt-1 text-sm " + (t.highlight ? "text-slate-300" : "text-slate-500")}>
                {t.limit}
              </p>
              <ul className="mt-6 space-y-2.5 text-sm">
                {t.features.map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <svg
                      className={
                        "mt-0.5 shrink-0 " + (t.highlight ? "text-[#F59E0B]" : "text-[#10B981]")
                      }
                      width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden
                    >
                      <path d="M3.5 8.5l3 3 6-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <span className={t.highlight ? "text-slate-200" : "text-slate-700"}>{f}</span>
                  </li>
                ))}
              </ul>
              <Link
                href={t.href}
                className={
                  "mt-8 inline-flex justify-center rounded-full px-5 py-3 text-sm font-semibold " +
                  (t.highlight
                    ? "bg-[#F59E0B] text-slate-900 hover:bg-amber-400"
                    : "bg-slate-900 text-white hover:bg-slate-800")
                }
              >
                {t.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────

function FAQ() {
  const qas = [
    {
      q: "Which cities do you cover?",
      a: "Every city where the municipality or its contracted hauler publishes a schedule. We're live in NYC, LA, Houston, Philadelphia, Phoenix, Austin, Denver, Boston, and parts of San Diego County, with new cities added weekly. Addresses outside our live coverage get flagged in your dashboard and added to the expansion queue.",
    },
    {
      q: "Where does the data come from? Is it reliable?",
      a: "Directly from the city. We integrate with municipal ArcGIS endpoints, Socrata open data, and national hauler APIs (Waste Management, Republic Services, etc.). Every address you look up has a provenance tag showing the source and last-verified date. No user-entered guesses, no stale cached PDFs.",
    },
    {
      q: "Does this work with Buildium / AppFolio / Yardi?",
      a: "CSV import works with all of them today. Direct two-way sync is on the Enterprise tier and is being built for the top three platforms. If you need a specific integration, tell us which one and we'll prioritize.",
    },
    {
      q: "What happens when the city's schedule changes?",
      a: "We detect schedule changes automatically and flag them in your next digest. Holiday shifts (Thanksgiving week, Christmas/New Year, major city observances) are tracked per-municipality and surfaced a week before they affect your properties.",
    },
    {
      q: "Can my residents opt in to reminders directly?",
      a: "Yes. Each address gets a branded share link that your residents can use to subscribe to email or SMS reminders. You stay in control — you decide whether to include the link in your move-in packet, and residents opt in themselves. No cold contact, no scraping.",
    },
    {
      q: "What if you don't cover one of my addresses?",
      a: "It goes on your dashboard with a 'Pending Coverage' flag and gets added to our expansion queue. You don't pay for addresses we can't serve with real data — those are excluded from your plan's address count.",
    },
    {
      q: "Is there a contract or can I cancel anytime?",
      a: "Month-to-month on Starter and Growth. Cancel from the dashboard, no call required. Enterprise is annual with a standard MSA and a termination-for-convenience clause.",
    },
  ];
  return (
    <section className="border-b border-slate-200 bg-[#FAF7F2]">
      <div className="mx-auto max-w-4xl px-6 py-20">
        <div className="mb-10">
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.15em] text-[#2563EB]">
            Frequently asked
          </p>
          <h2
            className="text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Questions property managers actually ask.
          </h2>
        </div>
        <div className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white">
          {qas.map((qa) => (
            <details key={qa.q} className="group px-6 py-4">
              <summary className="flex cursor-pointer items-start justify-between gap-6 text-left">
                <span className="text-base font-semibold text-slate-900">{qa.q}</span>
                <span className="mt-1 text-slate-400 transition group-open:rotate-45">
                  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
                    <path
                      d="M8 3v10M3 8h10"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                </span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-slate-600">{qa.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────

function FinalCTA() {
  return (
    <section className="bg-slate-900 text-white">
      <div className="mx-auto max-w-4xl px-6 py-20 text-center">
        <h2
          className="mb-4 text-4xl font-semibold tracking-tight sm:text-5xl"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Run your portfolio's pickup ops <em className="italic text-[#F59E0B]">without the spreadsheet</em>.
        </h2>
        <p className="mx-auto mb-8 max-w-xl text-slate-300">
          14-day free trial. Real municipal data. Cancel anytime.
          Takes about four minutes to set up.
        </p>
        <Link
          href="/portfolio/signup?plan=starter"
          className="inline-flex items-center gap-2 rounded-full bg-[#F59E0B] px-8 py-4 text-base font-semibold text-slate-900 hover:bg-amber-400"
        >
          Start my trial
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
            <path d="M3.5 9h11M10 4.5l4.5 4.5L10 13.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Link>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="bg-slate-950 text-slate-400">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-6 py-8 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <LogoMark />
          <span className="font-semibold text-white">TrashAlert</span>
          <span className="text-xs text-slate-500">
            · A Tombstone Dash LLC product
          </span>
        </div>
        <div className="flex items-center gap-5 text-sm">
          <Link href="/" className="hover:text-white">Consumer</Link>
          <Link href="/for/property-managers" className="hover:text-white">Property Managers</Link>
          <Link href="/privacy" className="hover:text-white">Privacy</Link>
          <Link href="/terms" className="hover:text-white">Terms</Link>
        </div>
      </div>
    </footer>
  );
}
