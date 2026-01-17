// PCSS Log API Client
const API_BASE = process.env.NEXT_PUBLIC_PCSS_API_URL || "https://api.pcss.r-e.kr"

export interface SummaryResponse {
  range: { start: string | null; end: string | null }
  filters: { type: string | null }
  total_events: number
  unique_ips: number
  first_ts: string | null
  last_ts: string | null
  by_type: { type: string; count: number }[]
  by_method: { method: string; count: number }[]
  top_paths: { path: string; count: number }[]
  top_referrers: { referer: string; count: number }[]
  top_user_agents: { user_agent: string; count: number }[]
  totalEvents: number
  uniqueIPs: number
  typeBreakdown: { type: string; count: number }[]
  methodBreakdown: { method: string; count: number }[]
  todayEvents: number
  weekEvents: number
}

export interface TimeseriesResponse {
  granularity: string
  range: { start: string | null; end: string | null }
  filters: { type: string | null }
  points: {
    bucket: string
    count: number
    unique_ips: number
    types: Record<string, number>
  }[]
  date: string
  count: number
  pageViews: number
  searches: number
  detailViews: number
  apiCalls: number
}

export interface TopResponse {
  field: string
  range: { start: string | null; end: string | null }
  filters: { type: string | null }
  items: { value: string; count: number; last_ts: string }[]
}

export interface TopItem {
  value: string
  count: number
}

export interface SearchOptionsResponse {
  range: { start: string | null; end: string | null }
  search_start_total: number
  by_option: { option: number; count: number }[]
  uncertainty: {
    min: number | null
    max: number | null
    avg: number | null
    histogram: { bucket: string; count: number }[]
  }
  year_ranges: {
    startyear_min: number | null
    startyear_max: number | null
    endyear_min: number | null
    endyear_max: number | null
    top_ranges: { startyear: number; endyear: number; count: number }[]
  }
  countOption: { countOption: boolean; count: number }[]
  selectedConferences: {
    top_conferences: { conf: string; count: number }[]
    selection_size_histogram: { k: number; count: number }[]
  }
  totalSearches: number
  avgUncertainty: number
  conferenceDistribution: { conference: string; count: number }[]
  yearRangeDistribution: { range: string; count: number }[]
  uncertaintyHistogram: { range: string; count: number }[]
}

export interface FunnelResponse {
  range: { start: string | null; end: string | null }
  unique_homepage_ips: number
  unique_search_ips: number
  unique_both_ips: number
  conversion_rate: number
  notes: string[]
  homeVisits: number
  searches: number
  detailViews: number
  homeToSearchRate: number
  searchToDetailRate: number
}

export interface RecentByIpResponse {
  ip: string
  range: { start: string | null; end: string | null }
  limit: number
  items: {
    ts: string
    type: string
    path: string | null
    method: string | null
    referer: string | null
    job_id: string | null
    options: Record<string, unknown> | null
  }[]
}

export interface HourlyData {
  hour: number
  count: number
}

export interface DailyData {
  day: string
  count: number
}

export interface RecentLog {
  _id: string
  type: string
  timestamp: string
  ip: string
  user_agent: string
  path: string
  referrer?: string
  method: string
  search_options?: Record<string, unknown>
}

function buildParams(params: Record<string, string | number | null | undefined>): string {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      searchParams.append(key, String(value))
    }
  })
  return searchParams.toString()
}

export async function fetchSummary(params?: {
  start?: string
  end?: string
  type?: string
  top_n?: number
}): Promise<SummaryResponse> {
  const query = params ? buildParams(params) : ""
  const res = await fetch(`${API_BASE}/logs/summary?${query}`)
  if (!res.ok) throw new Error("Failed to fetch summary")
  return res.json()
}

export async function fetchTimeseries(
  params?: {
    start?: string
    end?: string
    type?: string
    granularity?: "minute" | "hour" | "day" | "week" | "month"
  },
  days = 30,
): Promise<TimeseriesResponse[]> {
  const query = params ? buildParams(params) : ""
  const res = await fetch(`${API_BASE}/logs/timeseries?${query}&days=${days}`)
  if (!res.ok) throw new Error("Failed to fetch timeseries")
  return res.json()
}

export async function fetchTop(params: {
  field?: "ip" | "path" | "user_agent" | "referer" | "type"
  start?: string
  end?: string
  type?: string
  limit?: number
}): Promise<TopResponse> {
  const query = buildParams(params)
  const res = await fetch(`${API_BASE}/logs/top?${query}`)
  if (!res.ok) throw new Error("Failed to fetch top")
  return res.json()
}

export async function fetchSearchOptions(params?: {
  start?: string
  end?: string
}): Promise<SearchOptionsResponse> {
  const query = params ? buildParams(params) : ""
  const res = await fetch(`${API_BASE}/logs/search/options?${query}`)
  if (!res.ok) throw new Error("Failed to fetch search options")
  return res.json()
}

export async function fetchFunnel(params?: {
  start?: string
  end?: string
}): Promise<FunnelResponse> {
  const query = params ? buildParams(params) : ""
  const res = await fetch(`${API_BASE}/logs/funnel/home-to-search?${query}`)
  if (!res.ok) throw new Error("Failed to fetch funnel")
  return res.json()
}

export async function fetchRecentByIp(params: {
  ip: string
  start?: string
  end?: string
  limit?: number
}): Promise<RecentByIpResponse> {
  const query = buildParams(params)
  const res = await fetch(`${API_BASE}/logs/recent/by-ip?${query}`)
  if (!res.ok) throw new Error("Failed to fetch recent by ip")
  return res.json()
}

export async function fetchHourly(): Promise<HourlyData[]> {
  const res = await fetch("/api/stats/hourly")
  if (!res.ok) throw new Error("Failed to fetch hourly")
  return res.json()
}

export async function fetchDaily(): Promise<DailyData[]> {
  const res = await fetch("/api/stats/daily")
  if (!res.ok) throw new Error("Failed to fetch daily")
  return res.json()
}

export async function fetchRecent(ip?: string, limit = 50): Promise<RecentLog[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (ip) params.set("ip", ip)
  const res = await fetch(`/api/stats/recent?${params}`)
  if (!res.ok) throw new Error("Failed to fetch recent")
  return res.json()
}
