"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { TopItem } from "@/lib/api"

interface TopListProps {
  data: TopItem[] | null
  title: string
  isLoading: boolean
  maxItems?: number
}

export function TopList({ data, title, isLoading, maxItems = 10 }: TopListProps) {
  const items = data?.slice(0, maxItems) || []
  const maxCount = Math.max(...items.map((item) => item.count), 1)

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="flex h-[300px] items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-[300px] items-center justify-center text-muted-foreground">데이터 없음</div>
        ) : (
          <ScrollArea className="h-[300px]">
            <div className="space-y-1 p-4 pt-0">
              {items.map((item, index) => {
                const percentage = (item.count / maxCount) * 100

                return (
                  <div key={index} className="group relative rounded-lg p-2 hover:bg-secondary/50 transition-colors">
                    <div
                      className="absolute inset-y-0 left-0 rounded-lg bg-primary/10 transition-all"
                      style={{ width: `${percentage}%` }}
                    />
                    <div className="relative flex items-center justify-between gap-2">
                      <span className="text-sm font-mono truncate flex-1" title={item.value}>
                        {item.value.length > 40 ? `${item.value.slice(0, 40)}...` : item.value}
                      </span>
                      <Badge variant="secondary" className="shrink-0 font-mono">
                        {item.count.toLocaleString()}
                      </Badge>
                    </div>
                  </div>
                )
              })}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
