"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowRight, Users, Search, FileText } from "lucide-react"
import type { FunnelResponse } from "@/lib/api"

interface FunnelCardProps {
  data: FunnelResponse | null
  isLoading: boolean
}

export function FunnelCard({ data, isLoading }: FunnelCardProps) {
  if (isLoading) {
    return (
      <Card className="border-border bg-card">
        <CardContent className="flex h-[200px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </CardContent>
      </Card>
    )
  }

  if (!data) return null

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-medium">퍼널 분석 (홈 → 검색 → 상세)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between gap-4">
          {/* Home Visitors */}
          <div className="flex flex-col items-center gap-2 flex-1">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
              <Users className="h-7 w-7 text-primary" />
            </div>
            <span className="text-2xl font-bold">{data.homeVisits.toLocaleString()}</span>
            <span className="text-xs text-muted-foreground text-center">홈페이지 방문</span>
          </div>

          <div className="flex flex-col items-center">
            <ArrowRight className="h-6 w-6 text-muted-foreground" />
            <span className="text-xs text-primary font-medium">{data.homeToSearchRate.toFixed(1)}%</span>
          </div>

          {/* Searches */}
          <div className="flex flex-col items-center gap-2 flex-1">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent/10">
              <Search className="h-7 w-7 text-accent" />
            </div>
            <span className="text-2xl font-bold">{data.searches.toLocaleString()}</span>
            <span className="text-xs text-muted-foreground text-center">검색 수행</span>
          </div>

          <div className="flex flex-col items-center">
            <ArrowRight className="h-6 w-6 text-muted-foreground" />
            <span className="text-xs text-primary font-medium">{data.searchToDetailRate.toFixed(1)}%</span>
          </div>

          {/* Detail Views */}
          <div className="flex flex-col items-center gap-2 flex-1">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-chart-3/10">
              <FileText className="h-7 w-7 text-chart-3" />
            </div>
            <span className="text-2xl font-bold">{data.detailViews.toLocaleString()}</span>
            <span className="text-xs text-muted-foreground text-center">상세 조회</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
