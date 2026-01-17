"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import type { HourlyData } from "@/lib/api"

interface HourlyChartProps {
  data: HourlyData[] | null
  isLoading: boolean
}

export function HourlyChart({ data, isLoading }: HourlyChartProps) {
  const chartData =
    data?.map((item) => ({
      hour: `${item.hour}시`,
      count: item.count,
    })) || []

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-medium">시간대별 트래픽</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex h-[250px] items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <XAxis
                dataKey="hour"
                tick={{ fill: "oklch(0.65 0 0)", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                interval={2}
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
        )}
      </CardContent>
    </Card>
  )
}
