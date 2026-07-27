/** Typed server-side client for the Bidsa intelligence API.
 *
 * When API_URL is unset (e.g. a fresh Vercel import with no backend yet),
 * the client transparently switches to DEMO MODE: the same contract served
 * from a bundled snapshot of the historical warehouse (src/data/demo).
 */

const API_URL = process.env.API_URL;

/** True when serving from the bundled snapshot instead of a live backend. */
export const IS_DEMO = !API_URL;

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${res.status} on ${path}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

async function getOrNull<T>(path: string): Promise<T | null> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`API ${res.status} on ${path}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

// ---- types (mirror backend/app/schemas/intel.py) ---------------------------

export interface Overview {
  tenders: number;
  awards: number;
  total_award_halalas: number | null;
  total_award_sar: number | null;
  companies: number;
  agencies: number;
  avg_bidders: number | null;
  corpus_deadline_min: string | null;
  corpus_deadline_max: string | null;
}

export interface AgencyRow {
  agency_id: number;
  agency: string;
  tenders: number;
  total_award_halalas: number | null;
  total_award_sar: number | null;
  avg_bidders: number | null;
}

export interface TopWinnerRow {
  company_id: number | null;
  company: string | null;
  wins: number;
  total_award_halalas: number | null;
  total_award_sar: number | null;
  share_pct: number | null;
}

export interface ActivityShareRow {
  activity_id: number | null;
  activity: string | null;
  tenders: number;
  total_award_halalas: number | null;
  total_award_sar: number | null;
}

export interface AgencyProfile {
  agency_id: number;
  agency: string;
  tenders: number;
  total_award_halalas: number | null;
  total_award_sar: number | null;
  avg_bidders: number | null;
  single_bid_pct: number | null;
  top_winners: TopWinnerRow[];
  top_activities: ActivityShareRow[];
}

export interface PricingBenchmark {
  contracts: number;
  avg_halalas: number | null;
  median_halalas: number | null;
  p25_halalas: number | null;
  p75_halalas: number | null;
  min_halalas: number | null;
  max_halalas: number | null;
  avg_sar: number | null;
  median_sar: number | null;
  avg_bidders: number | null;
  filters: Record<string, unknown>;
}

export interface CompetitionRow {
  activity_id: number;
  activity: string;
  tenders: number;
  avg_bidders: number | null;
  single_bid_pct: number | null;
  median_award_sar: number | null;
}

export interface MatchmakingRow {
  tender_id: string;
  reference_number: string;
  title: string;
  agency: string | null;
  activity: string | null;
  region: string | null;
  winner_company_id: number | null;
  winner: string | null;
  award_halalas: number | null;
  award_sar: number | null;
  deadline: string | null;
  details_url: string | null;
}

export interface CompanySearchRow {
  company_id: number;
  name: string;
  wins: number;
  total_award_halalas: number | null;
  total_award_sar: number | null;
}

export interface CompanyProfile {
  company_id: number;
  name: string;
  wins: number;
  bids_participated: number;
  win_rate_pct: number | null;
  total_award_halalas: number | null;
  total_award_sar: number | null;
  top_agencies: AgencyRow[];
  top_activities: ActivityShareRow[];
}

export interface LookupItem {
  id: number;
  name: string;
  tenders: number;
}

export interface Lookups {
  activities: LookupItem[];
  regions: LookupItem[];
}

// ---- fetchers ---------------------------------------------------------------

const liveApi = {
  overview: () => get<Overview>("/api/v1/intel/overview"),
  agencies: (sort = "spend", limit = 30) =>
    get<AgencyRow[]>(`/api/v1/intel/agencies?sort=${sort}&limit=${limit}`),
  agencyProfile: (id: number) =>
    getOrNull<AgencyProfile>(`/api/v1/intel/agencies/${id}`),
  pricing: (params: URLSearchParams) =>
    get<PricingBenchmark>(`/api/v1/intel/pricing?${params.toString()}`),
  competition: (minTenders = 100, order = "least", limit = 30) =>
    get<CompetitionRow[]>(
      `/api/v1/intel/competition?min_tenders=${minTenders}&order=${order}&limit=${limit}`,
    ),
  matchmaking: (minAwardSar = 10_000_000, limit = 30) =>
    get<MatchmakingRow[]>(
      `/api/v1/intel/matchmaking?min_award_sar=${minAwardSar}&limit=${limit}`,
    ),
  searchCompanies: (q: string, limit = 30) =>
    get<CompanySearchRow[]>(
      `/api/v1/intel/companies?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),
  companyProfile: (id: number) =>
    getOrNull<CompanyProfile>(`/api/v1/intel/companies/${id}`),
  lookups: () => get<Lookups>("/api/v1/intel/lookups"),
};

// Lazy import keeps the snapshot out of the bundle when a live API is used.
function resolveApi(): typeof liveApi {
  if (IS_DEMO) {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { demoApi } = require("@/lib/demo") as typeof import("@/lib/demo");
    return demoApi;
  }
  return liveApi;
}

export const api = resolveApi();
