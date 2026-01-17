"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts"
import type { TimeseriesResponse } from "@/lib/api"

interface TimeseriesChartProps {
  data: TimeseriesResponse[] | null
  isLoading: boolean
}

export function TimeseriesChart({ data, isLoading }: TimeseriesChartProps) {
  const chartData =
    data?.map((point) => ({
      time: new Date(point.date).toLocaleDateString("ko-KR", {
        month: "short",
        day: "numeric",
      }),
      total: point.count,
      pageViews: point.pageViews,
      searches: point.searches,
      detailViews: point.detailViews,
    })) || []

  return (
    <Card className="border-border bg-card col-span-full">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg font-medium">
          <span className="flex h-3 w-3 rounded-full bg-primary" />
          요청 수 추이
          <span className="ml-auto text-sm font-normal text-muted-foreground">일별</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex h-[300px] items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="oklch(0.7 0.15 200)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="oklch(0.7 0.15 200)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorPageViews" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="oklch(0.75 0.18 85)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="oklch(0.75 0.18 85)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorSearches" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="oklch(0.65 0.18 150)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="oklch(0.65 0.18 150)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.28 0.01 270)" vertical={false} />
              <XAxis
                dataKey="time"
                tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }} tickLine={false} axisLine={false} width={50} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "oklch(0.17 0.01 270)",
                  border: "1px solid oklch(0.28 0.01 270)",
                  borderRadius: "8px",
                  color: "oklch(0.95 0 0)",
                }}
                labelStyle={{ color: "oklch(0.65 0 0)" }}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="total"
                stroke="oklch(0.7 0.15 200)"
                strokeWidth={2}
                fill="url(#colorTotal)"
                name="전체"
              />
              <Area
                type="monotone"
                dataKey="pageViews"
                stroke="oklch(0.75 0.18 85)"
                strokeWidth={2}
                fill="url(#colorPageViews)"
                name="페이지뷰"
              />
              <Area
                type="monotone"
                dataKey="searches"
                stroke="oklch(0.65 0.18 150)"
                strokeWidth={2}
                fill="url(#colorSearches)"
                name="검색"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
