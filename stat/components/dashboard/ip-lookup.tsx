"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Search, Clock, Globe } from "lucide-react"
import { fetchRecent, type RecentLog } from "@/lib/api"

export function IpLookup() {
  const [ip, setIp] = useState("")
  const [data, setData] = useState<RecentLog[] | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async () => {
    if (!ip.trim()) return

    setIsLoading(true)
    setError(null)

    try {
      const result = await fetchRecent(ip.trim(), 100)
      setData(result)
    } catch {
      setError("IP 조회에 실패했습니다.")
      setData(null)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg font-medium">
          <Globe className="h-5 w-5" />
          IP 별 로그 조회
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2 mb-4">
          <Input
            placeholder="IP 주소 입력 (예: 122.202.51.93)"
            value={ip}
            onChange={(e) => setIp(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="bg-secondary border-border font-mono"
          />
          <Button onClick={handleSearch} disabled={isLoading || !ip.trim()}>
            {isLoading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
            ) : (
              <Search className="h-4 w-4" />
            )}
          </Button>
        </div>

        {error && <p className="text-sm text-destructive mb-4">{error}</p>}

        {data && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">조회 결과</span>
              <Badge variant="outline">{data.length}건</Badge>
            </div>

            <ScrollArea className="h-[300px] rounded-lg border border-border">
              <div className="space-y-1 p-2">
                {data.map((item, index) => (
                  <div
                    key={index}
                    className="flex items-start gap-3 rounded-lg p-2 hover:bg-secondary/50 transition-colors"
                  >
                    <Clock className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="secondary" className="text-xs">
                          {item.type}
                        </Badge>
                        {item.method && (
                          <Badge variant="outline" className="text-xs">
                            {item.method}
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {new Date(item.timestamp).toLocaleString("ko-KR")}
                        </span>
                      </div>
                      {item.path && (
                        <p className="text-sm font-mono text-muted-foreground truncate mt-1">{item.path}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
