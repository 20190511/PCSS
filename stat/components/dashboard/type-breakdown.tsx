"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

interface TypeBreakdownProps {
  data: { type: string; count: number }[]
  title: string
  isLoading: boolean
}

const COLORS = [
  "oklch(0.7 0.15 200)",
  "oklch(0.75 0.18 85)",
  "oklch(0.65 0.18 150)",
  "oklch(0.7 0.15 320)",
  "oklch(0.6 0.2 25)",
]

export function TypeBreakdown({ data, title, isLoading }: TypeBreakdownProps) {
  const chartData = data.slice(0, 8).map((item) => ({
    name: item.type || "(empty)",
    value: item.count,
  }))

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex h-[250px] items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
              <XAxis type="number" tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis
                dataKey="name"
                type="category"
                tick={{ fill: "oklch(0.65 0 0)", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={100}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "oklch(0.17 0.01 270)",
                  border: "1px solid oklch(0.28 0.01 270)",
                  borderRadius: "8px",
                  color: "oklch(0.95 0 0)",
                }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {chartData.map((_, index) => (
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
