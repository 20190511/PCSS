"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react"
import { useRecentLogs } from "@/lib/hooks/use-log-data"
import { useFilter } from "@/lib/filter-context"

const typeColors: Record<string, string> = {
  homepage: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  search_start: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  search_complete: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  api_call: "bg-amber-500/10 text-amber-400 border-amber-500/20",
}

export function RecentLogsTable() {
  const [page, setPage] = useState(1)
  const { startDateISO, endDateISO, logType } = useFilter()
  const { data, isLoading, error } = useRecentLogs(startDateISO, endDateISO, logType, page, 10)

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString("ko-KR", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
  }

  const parseUserAgent = (ua: string) => {
    if (ua.includes("Edg")) return "Edge"
    if (ua.includes("Chrome")) return "Chrome"
    if (ua.includes("Firefox")) return "Firefox"
    if (ua.includes("Safari")) return "Safari"
    return "Other"
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium text-foreground">최근 로그</CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8 bg-transparent"
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1 || isLoading}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm text-muted-foreground">
              {data ? `${page} / ${data.totalPages || 1}` : `페이지 ${page}`}
            </span>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8 bg-transparent"
              onClick={() => setPage(page + 1)}
              disabled={isLoading || (data && page >= data.totalPages)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : error || !data || data.logs.length === 0 ? (
          <div className="flex items-center justify-center h-64">
            <span className="text-sm text-muted-foreground">데이터가 없습니다</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground">시간</TableHead>
                  <TableHead className="text-muted-foreground">타입</TableHead>
                  <TableHead className="text-muted-foreground">IP</TableHead>
                  <TableHead className="text-muted-foreground">메소드</TableHead>
                  <TableHead className="text-muted-foreground">경로</TableHead>
                  <TableHead className="text-muted-foreground">브라우저</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.logs.map((log) => (
                  <TableRow key={log.id} className="border-border">
                    <TableCell className="text-foreground font-mono text-sm">{formatDate(log.ts)}</TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={typeColors[log.type] || "bg-secondary text-secondary-foreground"}
                      >
                        {log.type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground font-mono text-sm">{log.ip}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="font-mono">
                        {log.method}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground font-mono text-sm max-w-[200px] truncate">
                      {log.path}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">{parseUserAgent(log.user_agent)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
