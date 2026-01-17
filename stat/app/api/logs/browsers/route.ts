import { type NextRequest, NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

function parseUserAgent(ua: string): string {
  if (ua.includes("Edg")) return "Edge"
  if (ua.includes("Chrome")) return "Chrome"
  if (ua.includes("Firefox")) return "Firefox"
  if (ua.includes("Safari")) return "Safari"
  return "기타"
}

export async function GET(request: NextRequest) {
  try {
    const db = await getDatabase()
    const collection = db.collection("access_logs")

    const searchParams = request.nextUrl.searchParams
    const startDate = searchParams.get("startDate")
    const endDate = searchParams.get("endDate")

    // 날짜 필터 구성
    const matchStage: Record<string, unknown> = {}
    if (startDate || endDate) {
      matchStage.ts = {}
      if (startDate) (matchStage.ts as Record<string, unknown>).$gte = new Date(startDate)
      if (endDate) (matchStage.ts as Record<string, unknown>).$lte = new Date(endDate)
    }

    // 모든 로그의 user_agent 가져오기
    const logs = await collection
      .find(Object.keys(matchStage).length > 0 ? matchStage : {})
      .project({ user_agent: 1 })
      .toArray()

    // 브라우저별 집계
    const browserCounts: Record<string, number> = {}
    let total = 0

    logs.forEach((log) => {
      const browser = parseUserAgent(log.user_agent || "")
      browserCounts[browser] = (browserCounts[browser] || 0) + 1
      total++
    })

    // 정렬 및 퍼센트 계산
    const browserData = Object.entries(browserCounts)
      .map(([name, count]) => ({
        name,
        count,
        percentage: total > 0 ? Math.round((count / total) * 100) : 0,
      }))
      .sort((a, b) => b.count - a.count)

    return NextResponse.json(browserData)
  } catch (error) {
    console.error("Browsers API Error:", error)
    return NextResponse.json({ error: "Failed to fetch browser data" }, { status: 500 })
  }
}
