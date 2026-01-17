"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import type { SearchOptionsResponse } from "@/lib/api"

interface SearchOptionsStatsProps {
  data: SearchOptionsResponse | null
  isLoading: boolean
}

const COLORS = [
  "oklch(0.7 0.15 200)",
  "oklch(0.75 0.18 85)",
  "oklch(0.65 0.18 150)",
  "oklch(0.7 0.15 320)",
  "oklch(0.6 0.2 25)",
]

export function SearchOptionsStats({ data, isLoading }: SearchOptionsStatsProps) {
  if (isLoading) {
    return (
      <Card className="border-border bg-card col-span-full">
        <CardContent className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </CardContent>
      </Card>
    )
  }

  if (!data) return null

  const topConfs = data.conferenceDistribution.slice(0, 10)
  const uncertaintyHist = data.uncertaintyHistogram

  return (
    <div className="col-span-full grid gap-4 md:grid-cols-2">
      {/* Top Conferences */}
      <Card className="border-border bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-medium">인기 학회 선택</CardTitle>
        </CardHeader>
        <CardContent>
          {topConfs.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={topConfs} layout="vertical" margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                <XAxis
                  type="number"
                  tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  dataKey="conference"
                  type="category"
                  tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  width={60}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "oklch(0.17 0.01 270)",
                    border: "1px solid oklch(0.28 0.01 270)",
                    borderRadius: "8px",
                    color: "oklch(0.95 0 0)",
                  }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {topConfs.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[280px] items-center justify-center text-muted-foreground">데이터 없음</div>
          )}
        </CardContent>
      </Card>

      {/* Uncertainty Distribution */}
      <Card className="border-border bg-card">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg font-medium">Uncertainty 분포</CardTitle>
            <Badge variant="outline">평균: {data.avgUncertainty?.toFixed(2) || "-"}</Badge>
          </div>
        </CardHeader>
        <CardContent>
          {uncertaintyHist.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={uncertaintyHist} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                <XAxis
                  dataKey="range"
                  tick={{ fill: "oklch(0.65 0 0)", fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }} tickLine={false} axisLine={false} width={40} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "oklch(0.17 0.01 270)",
                    border: "1px solid oklch(0.28 0.01 270)",
                    borderRadius: "8px",
                    color: "oklch(0.95 0 0)",
                  }}
                />
                <Bar dataKey="count" fill="oklch(0.7 0.15 200)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[280px] items-center justify-center text-muted-foreground">데이터 없음</div>
          )}
        </CardContent>
      </Card>

      {/* Year Range Distribution */}
      <Card className="border-border bg-card md:col-span-2">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-medium">연도 범위 분포</CardTitle>
        </CardHeader>
        <CardContent>
          {data.yearRangeDistribution.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              {data.yearRangeDistribution.map((item, index) => (
                <div
                  key={item.range}
                  className="rounded-lg p-4 text-center"
                  style={{ backgroundColor: `color-mix(in oklch, ${COLORS[index % COLORS.length]} 20%, transparent)` }}
                >
                  <p className="text-2xl font-bold">{item.count.toLocaleString()}</p>
                  <p className="text-xs text-muted-foreground">{item.range}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex h-[100px] items-center justify-center text-muted-foreground">데이터 없음</div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
