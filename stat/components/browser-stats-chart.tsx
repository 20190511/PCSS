"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Loader2 } from "lucide-react"
import { useBrowserStats } from "@/lib/hooks/use-log-data"
import { useFilter } from "@/lib/filter-context"

export function BrowserStatsChart() {
  const { startDateISO, endDateISO } = useFilter()
  const { data, isLoading, error } = useBrowserStats(startDateISO, endDateISO)

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium text-foreground">브라우저 분포</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : error || !data || data.length === 0 ? (
          <div className="flex items-center justify-center h-48">
            <span className="text-sm text-muted-foreground">데이터가 없습니다</span>
          </div>
        ) : (
          data.map((browser) => (
            <div key={browser.name} className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-foreground font-medium">{browser.name}</span>
                <span className="text-muted-foreground">
                  {browser.count.toLocaleString()} ({browser.percentage}%)
                </span>
              </div>
              <Progress value={browser.percentage} className="h-2" />
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}
