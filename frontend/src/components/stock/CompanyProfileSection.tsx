// Spec: specs/029-company-profile-tweaks/contracts/company-profile-api.md (US2)
//
// Topmost section of the Overview tab (FR-010). Price/change/change%/volume
// are derived from the stock's own price bars — never from the profile
// record — so this section can never disagree with the Charts tab
// (research R7, FR-011a/FR-011b): both read the same underlying data.
import type { CompanyProfile, OHLCVBar } from "../../api/types";
import CompanyLogo from "../shared/CompanyLogo";
import { formatCompact } from "../earnings/EarningsTable";
import { formatDate, relativeTime } from "../../lib/time";

function priceStats(bars: OHLCVBar[] | undefined) {
  if (!bars || bars.length === 0) return null;
  const last = bars[bars.length - 1];
  const prev = bars.length > 1 ? bars[bars.length - 2] : null;
  const change = prev ? last.close - prev.close : null;
  const changePct = prev && prev.close !== 0 ? (change! / prev.close) * 100 : null;
  return { price: last.close, volume: last.volume, change, changePct };
}

function formatPct(v: number | null): string {
  if (v === null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function formatSignedPrice(v: number | null): string {
  if (v === null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}`;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-sm text-zinc-200">{value}</div>
    </div>
  );
}

export default function CompanyProfileSection({
  profile,
  isError,
  dailyBars,
}: {
  profile: CompanyProfile | undefined;
  isError: boolean;
  dailyBars: OHLCVBar[] | undefined;
}) {
  if (isError || !profile) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Company Profile
        </h2>
        <p className="text-sm text-zinc-500">Profile unavailable for this ticker.</p>
      </section>
    );
  }

  const stats = priceStats(dailyBars);
  const isCompany = !profile.is_etf && !profile.is_fund;
  const fetchedAt = profile.fetched_at ? relativeTime(profile.fetched_at) : null;

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <CompanyLogo ticker={profile.ticker} src={profile.logo_url} size="lg" />
          <div>
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-lg font-semibold text-white">{profile.name ?? profile.ticker}</span>
              {profile.exchange && <span className="text-xs text-zinc-500">{profile.exchange}</span>}
            </div>
            <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-zinc-400">
              {profile.sector && <span>{profile.sector}</span>}
              {profile.industry && <span>{profile.industry}</span>}
              {profile.country && <span>{profile.country}</span>}
            </div>
          </div>
        </div>
        {profile.website && (
          <a
            href={profile.website}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-sky-400 hover:text-sky-300"
          >
            {profile.website.replace(/^https?:\/\//, "")}
          </a>
        )}
      </div>

      {stats && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Price" value={`$${stats.price.toFixed(2)}`} />
          <Stat
            label="Change"
            value={`${formatSignedPrice(stats.change)} (${formatPct(stats.changePct)})`}
          />
          <Stat label="Volume" value={stats.volume.toLocaleString()} />
          <Stat label="Market Cap" value={formatCompact(profile.market_cap)} />
          <Stat label="Beta" value={profile.beta?.toFixed(2) ?? "—"} />
          <Stat label="Last Dividend" value={profile.last_dividend != null ? `$${profile.last_dividend.toFixed(2)}` : "—"} />
          <Stat
            label="52-Week Range"
            value={
              profile.range_low != null && profile.range_high != null
                ? `$${profile.range_low.toFixed(2)} – $${profile.range_high.toFixed(2)}`
                : "—"
            }
          />
          <Stat label="Avg. Volume" value={profile.average_volume?.toLocaleString() ?? "—"} />
        </div>
      )}

      {isCompany && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="CEO" value={profile.ceo ?? "—"} />
          <Stat label="Employees" value={profile.full_time_employees?.toLocaleString() ?? "—"} />
          <Stat label="IPO Date" value={profile.ipo_date ? formatDate(profile.ipo_date) ?? profile.ipo_date : "—"} />
        </div>
      )}

      {profile.description && (
        <p className="text-sm leading-relaxed text-zinc-300">{profile.description}</p>
      )}

      {fetchedAt && <p className="mt-3 text-[11px] text-zinc-600">profile as of {fetchedAt}</p>}
    </section>
  );
}
