"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import type { DailyData } from "@/lib/api"

interface DailyChartProps {
  data: DailyData[] | null
  isLoading: boolean
}

const COLORS = [
  "oklch(0.6 0.15 200)",
  "oklch(0.7 0.15 200)",
  "oklch(0.7 0.15 200)",
  "oklch(0.7 0.15 200)",
  "oklch(0.7 0.15 200)",
  "oklch(0.7 0.15 200)",
  "oklch(0.6 0.15 200)",
]

export function DailyChart({ data, isLoading }: DailyChartProps) {
  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-medium">요일별 트래픽</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex h-[250px] items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data || []} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <XAxis dataKey="day" tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }} tickLine={false} axisLine={false} width={40} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "oklch(0.17 0.01 270)",
                  border: "1px solid oklch(0.28 0.01 270)",
                  borderRadius: "8px",
                  color: "oklch(0.95 0 0)",
                }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {(data || []).map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
