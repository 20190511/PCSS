import { Suspense } from "react"
import { DashboardHeader } from "@/components/dashboard-header"
import { StatsCards } from "@/components/stats-cards"
import { DailyVisitorsChart } from "@/components/daily-visitors-chart"
import { LogTypeChart } from "@/components/log-type-chart"
import { HourlyTrafficChart } from "@/components/hourly-traffic-chart"
import { BrowserStatsChart } from "@/components/browser-stats-chart"
import { RecentLogsTable } from "@/components/recent-logs-table"
import { Skeleton } from "@/components/ui/skeleton"
import { FilterProvider } from "@/lib/filter-context"

export default function DashboardPage() {
  return (
    <FilterProvider>
      <div className="min-h-screen bg-background">
        <DashboardHeader />
        <main className="container mx-auto px-4 py-6 space-y-6">
          <Suspense fallback={<StatsCardsSkeleton />}>
            <StatsCards />
          </Suspense>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Suspense fallback={<ChartSkeleton />}>
              <DailyVisitorsChart />
            </Suspense>
            <Suspense fallback={<ChartSkeleton />}>
              <LogTypeChart />
            </Suspense>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Suspense fallback={<ChartSkeleton />}>
              <HourlyTrafficChart />
            </Suspense>
            <Suspense fallback={<ChartSkeleton />}>
              <BrowserStatsChart />
            </Suspense>
          </div>

          <Suspense fallback={<TableSkeleton />}>
            <RecentLogsTable />
          </Suspense>
        </main>
      </div>
    </FilterProvider>
  )
}

function StatsCardsSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {[...Array(4)].map((_, i) => (
        <Skeleton key={i} className="h-28 rounded-lg" />
      ))}
    </div>
  )
}

function ChartSkeleton() {
  return <Skeleton className="h-80 rounded-lg" />
}

function TableSkeleton() {
  return <Skeleton className="h-96 rounded-lg" />
}
