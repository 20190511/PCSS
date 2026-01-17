"use client"

import { Activity, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface HeaderProps {
  granularity: string
  onGranularityChange: (value: string) => void
  dateRange: string
  onDateRangeChange: (value: string) => void
  onRefresh: () => void
  isLoading: boolean
}

export function Header({
  granularity,
  onGranularityChange,
  dateRange,
  onDateRangeChange,
  onRefresh,
  isLoading,
}: HeaderProps) {
  return (
    <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Activity className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">PCSS Log Analytics</h1>
              <p className="text-sm text-muted-foreground">실시간 로그 통계 대시보드</p>
            </div>
          </div>

          {/* Simplified header without date range selection (DB handles it) */}
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isLoading}
            className="border-border bg-transparent"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
            새로고침
          </Button>
        </div>
      </div>
    </header>
  )
}
