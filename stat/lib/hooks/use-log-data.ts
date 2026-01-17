"use client"

import useSWR from "swr"
import type { StatsData, DailyVisitorData, LogTypeData, HourlyData, BrowserData, LogEntry } from "@/lib/types"

const fetcher = (url: string) => fetch(url).then((res) => res.json())

export function useStats(startDate?: string, endDate?: string) {
  const params = new URLSearchParams()
  if (startDate) params.set("startDate", startDate)
  if (endDate) params.set("endDate", endDate)

  return useSWR<StatsData>(`/api/logs/stats?${params.toString()}`, fetcher)
}

export function useDailyVisitors(startDate?: string, endDate?: string) {
  const params = new URLSearchParams()
  if (startDate) params.set("startDate", startDate)
  if (endDate) params.set("endDate", endDate)

  return useSWR<DailyVisitorData[]>(`/api/logs/daily?${params.toString()}`, fetcher)
}

export function useLogTypes(startDate?: string, endDate?: string) {
  const params = new URLSearchParams()
  if (startDate) params.set("startDate", startDate)
  if (endDate) params.set("endDate", endDate)

  return useSWR<LogTypeData[]>(`/api/logs/types?${params.toString()}`, fetcher)
}

export function useHourlyTraffic(startDate?: string, endDate?: string) {
  const params = new URLSearchParams()
  if (startDate) params.set("startDate", startDate)
  if (endDate) params.set("endDate", endDate)

  return useSWR<HourlyData[]>(`/api/logs/hourly?${params.toString()}`, fetcher)
}

export function useBrowserStats(startDate?: string, endDate?: string) {
  const params = new URLSearchParams()
  if (startDate) params.set("startDate", startDate)
  if (endDate) params.set("endDate", endDate)

  return useSWR<BrowserData[]>(`/api/logs/browsers?${params.toString()}`, fetcher)
}

export function useRecentLogs(startDate?: string, endDate?: string, type?: string, page = 1, limit = 10) {
  const params = new URLSearchParams()
  if (startDate) params.set("startDate", startDate)
  if (endDate) params.set("endDate", endDate)
  if (type) params.set("type", type)
  params.set("page", page.toString())
  params.set("limit", limit.toString())

  return useSWR<{
    logs: LogEntry[]
    totalCount: number
    totalPages: number
    currentPage: number
  }>(`/api/logs/recent?${params.toString()}`, fetcher)
}
