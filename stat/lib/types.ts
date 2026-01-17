export interface LogEntry {
  _id: string
  ts: string
  type: string
  ip: string
  method: string
  path: string
  user_agent: string
  [key: string]: unknown
}

export interface StatsData {
  totalVisitors: number
  pageViews: number
  searchRequests: number
  avgSessionTime: string
  visitorChange: number
  pageViewChange: number
  searchChange: number
  sessionChange: number
}

export interface DailyVisitorData {
  date: string
  visitors: number
  pageviews: number
}

export interface LogTypeData {
  name: string
  value: number
  label: string
}

export interface HourlyData {
  hour: string
  requests: number
}

export interface BrowserData {
  name: string
  percentage: number
  count: number
}

export interface FilterParams {
  startDate?: string
  endDate?: string
  type?: string
  page?: number
  limit?: number
}
