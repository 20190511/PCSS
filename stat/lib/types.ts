export interface LogDocument {
  _id: string
  type: "page_view" | "search" | "detail_view" | "api_call"
  timestamp: Date
  ip: string
  user_agent: string
  path: string
  referrer?: string
  method: string
  search_options?: {
    conferences?: string[]
    uncertainty?: number
    year_start?: number
    year_end?: number
    query?: string
  }
}

export interface SummaryStats {
  totalEvents: number
  uniqueIPs: number
  typeBreakdown: { type: string; count: number }[]
  methodBreakdown: { method: string; count: number }[]
  todayEvents: number
  weekEvents: number
}

export interface TimeSeriesData {
  date: string
  count: number
  pageViews: number
  searches: number
  detailViews: number
}

export interface TopItem {
  value: string
  count: number
}

export interface SearchOptionStats {
  totalSearches: number
  avgUncertainty: number
  conferenceDistribution: { conference: string; count: number }[]
  yearRangeDistribution: { range: string; count: number }[]
  uncertaintyHistogram: { range: string; count: number }[]
}

export interface FunnelData {
  homeVisits: number
  searches: number
  detailViews: number
  homeToSearchRate: number
  searchToDetailRate: number
}

export interface HourlyDistribution {
  hour: number
  count: number
}

export interface DailyDistribution {
  day: string
  count: number
}
