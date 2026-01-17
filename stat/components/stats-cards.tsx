"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Users, Eye, Search, TrendingUp, Loader2 } from "lucide-react"
import { useStats } from "@/lib/hooks/use-log-data"
import { useFilter } from "@/lib/filter-context"

export function StatsCards() {
  const { startDateISO, endDateISO } = useFilter()
  const { data, isLoading, error } = useStats(startDateISO, endDateISO)

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="bg-card border-border">
            <CardContent className="p-5 flex items-center justify-center h-28">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="bg-card border-border">
            <CardContent className="p-5 flex items-center justify-center h-28">
              <span className="text-sm text-muted-foreground">데이터 로드 실패</span>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const stats = [
    {
      title: "총 방문자",
      value: data.totalVisitors.toLocaleString(),
      change: data.visitorChange,
      icon: Users,
      description: "고유 IP 기준",
    },
    {
      title: "페이지뷰",
      value: data.pageViews.toLocaleString(),
      change: data.pageViewChange,
      icon: Eye,
      description: "전체 요청 수",
    },
    {
      title: "검색 요청",
      value: data.searchRequests.toLocaleString(),
      change: data.searchChange,
      icon: Search,
      description: "search_start 이벤트",
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat) => (
        <Card key={stat.title} className="bg-card border-border">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">{stat.title}</p>
                <p className="text-2xl font-semibold text-foreground">{stat.value}</p>
                <p className="text-xs text-muted-foreground">{stat.description}</p>
              </div>
              <div className="flex flex-col items-end gap-2">
                <div className="p-2 rounded-lg bg-secondary">
                  <stat.icon className="w-4 h-4 text-muted-foreground" />
                </div>
                <span className={`text-xs font-medium ${stat.change >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {stat.change >= 0 ? "+" : ""}
                  {stat.change}%
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
