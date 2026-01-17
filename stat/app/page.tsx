"use client"

import { Suspense, useState } from "react"
import useSWR from "swr"
import { Activity, Users, FileText, TrendingUp } from "lucide-react"
import { Header } from "@/components/dashboard/header"
import { StatCard } from "@/components/dashboard/stat-card"
import { TimeseriesChart } from "@/components/dashboard/timeseries-chart"
import { TypeBreakdown } from "@/components/dashboard/type-breakdown"
import { TopList } from "@/components/dashboard/top-list"
import { FunnelCard } from "@/components/dashboard/funnel-card"
import { SearchOptionsStats } from "@/components/dashboard/search-options-stats"
import { IpLookup } from "@/components/dashboard/ip-lookup"
import { HourlyChart } from "@/components/dashboard/hourly-chart"
import { DailyChart } from "@/components/dashboard/daily-chart"
import {
  fetchSummary,
  fetchTimeseries,
  fetchFunnel,
  fetchSearchOptions,
  fetchTop,
  fetchHourly,
  fetchDaily,
} from "@/lib/api"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

function DashboardContent() {
  const [refreshKey, setRefreshKey] = useState(0)

  const { data: summary, isLoading: summaryLoading } = useSWR(["summary", refreshKey], () => fetchSummary(), {
    revalidateOnFocus: false,
  })

  const { data: timeseries, isLoading: timeseriesLoading } = useSWR(
    ["timeseries", refreshKey],
    () => fetchTimeseries(30),
    { revalidateOnFocus: false },
  )

  const { data: funnel, isLoading: funnelLoading } = useSWR(["funnel", refreshKey], () => fetchFunnel(), {
    revalidateOnFocus: false,
  })

  const { data: searchOptions, isLoading: searchOptionsLoading } = useSWR(
    ["searchOptions", refreshKey],
    () => fetchSearchOptions(),
    { revalidateOnFocus: false },
  )

  const { data: topPaths, isLoading: topPathsLoading } = useSWR(["topPaths", refreshKey], () => fetchTop("path", 10), {
    revalidateOnFocus: false,
  })

  const { data: topReferrers, isLoading: topReferrersLoading } = useSWR(
    ["topReferrers", refreshKey],
    () => fetchTop("referrer", 10),
    { revalidateOnFocus: false },
  )

  const { data: topUserAgents, isLoading: topUserAgentsLoading } = useSWR(
    ["topUserAgents", refreshKey],
    () => fetchTop("user_agent", 10),
    { revalidateOnFocus: false },
  )

  const { data: topIps, isLoading: topIpsLoading } = useSWR(["topIps", refreshKey], () => fetchTop("ip", 10), {
    revalidateOnFocus: false,
  })

  const { data: hourly, isLoading: hourlyLoading } = useSWR(["hourly", refreshKey], () => fetchHourly(), {
    revalidateOnFocus: false,
  })

  const { data: daily, isLoading: dailyLoading } = useSWR(["daily", refreshKey], () => fetchDaily(), {
    revalidateOnFocus: false,
  })

  const handleRefresh = () => {
    setRefreshKey((prev) => prev + 1)
  }

  const isLoading = summaryLoading || timeseriesLoading

  return (
    <div className="min-h-screen bg-background">
      <Header onRefresh={handleRefresh} isLoading={isLoading} />

      <main className="container mx-auto px-4 py-6">
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="bg-secondary border border-border">
            <TabsTrigger value="overview">개요</TabsTrigger>
            <TabsTrigger value="traffic">트래픽 분석</TabsTrigger>
            <TabsTrigger value="search">검색 분석</TabsTrigger>
            <TabsTrigger value="details">상세 조회</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            {/* Stats Cards */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <StatCard title="총 이벤트" value={summary?.totalEvents || 0} icon={Activity} />
              <StatCard title="고유 IP" value={summary?.uniqueIPs || 0} icon={Users} />
              <StatCard title="오늘 이벤트" value={summary?.todayEvents || 0} icon={TrendingUp} />
              <StatCard title="이번 주 이벤트" value={summary?.weekEvents || 0} icon={FileText} />
            </div>

            {/* Timeseries Chart */}
            <TimeseriesChart data={timeseries ?? null} isLoading={timeseriesLoading} />

            {/* Breakdown Charts */}
            <div className="grid gap-4 md:grid-cols-2">
              <TypeBreakdown data={summary?.typeBreakdown || []} title="타입별 분포" isLoading={summaryLoading} />
              <TypeBreakdown
                data={summary?.methodBreakdown?.map((m) => ({ type: m.method, count: m.count })) || []}
                title="HTTP 메소드 분포"
                isLoading={summaryLoading}
              />
            </div>

            {/* Funnel */}
            <FunnelCard data={funnel ?? null} isLoading={funnelLoading} />
          </TabsContent>

          <TabsContent value="traffic" className="space-y-6">
            {/* Hourly & Daily Charts */}
            <div className="grid gap-4 md:grid-cols-2">
              <HourlyChart data={hourly ?? null} isLoading={hourlyLoading} />
              <DailyChart data={daily ?? null} isLoading={dailyLoading} />
            </div>

            {/* Top Lists */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <TopList data={topPaths ?? null} title="인기 경로" isLoading={topPathsLoading} />
              <TopList data={topReferrers ?? null} title="인기 Referrer" isLoading={topReferrersLoading} />
              <TopList data={topUserAgents ?? null} title="인기 User Agent" isLoading={topUserAgentsLoading} />
              <TopList data={topIps ?? null} title="인기 IP" isLoading={topIpsLoading} />
            </div>
          </TabsContent>

          <TabsContent value="search" className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <StatCard title="총 검색 수" value={searchOptions?.totalSearches || 0} icon={Activity} />
              <StatCard
                title="평균 Uncertainty"
                value={searchOptions?.avgUncertainty?.toFixed(2) || "-"}
                icon={FileText}
              />
              <StatCard title="학회 종류" value={searchOptions?.conferenceDistribution?.length || 0} icon={Users} />
            </div>

            <SearchOptionsStats data={searchOptions ?? null} isLoading={searchOptionsLoading} />
          </TabsContent>

          <TabsContent value="details" className="space-y-6">
            <div className="grid gap-4 lg:grid-cols-2">
              <IpLookup />
              <TopList
                data={topUserAgents ?? null}
                title="전체 User Agent 목록"
                isLoading={topUserAgentsLoading}
                maxItems={20}
              />
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

export default function Dashboard() {
  return (
    <Suspense fallback={<DashboardLoading />}>
      <DashboardContent />
    </Suspense>
  )
}

function DashboardLoading() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="text-muted-foreground">로딩 중...</p>
      </div>
    </div>
  )
}
