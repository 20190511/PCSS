import { type NextRequest, NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

export async function GET(request: NextRequest) {
  try {
    const db = await getDatabase()
    const collection = db.collection("access_logs")

    const searchParams = request.nextUrl.searchParams
    const startDate = searchParams.get("startDate")
    const endDate = searchParams.get("endDate")

    // 날짜 필터 구성
    const dateFilter: Record<string, unknown> = {}
    if (startDate || endDate) {
      dateFilter.ts = {}
      if (startDate) (dateFilter.ts as Record<string, unknown>).$gte = new Date(startDate)
      if (endDate) (dateFilter.ts as Record<string, unknown>).$lte = new Date(endDate)
    }

    // 이전 기간 계산 (비교용)
    const currentStart = startDate ? new Date(startDate) : new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
    const currentEnd = endDate ? new Date(endDate) : new Date()
    const periodDiff = currentEnd.getTime() - currentStart.getTime()
    const previousStart = new Date(currentStart.getTime() - periodDiff)
    const previousEnd = new Date(currentStart.getTime())

    // 현재 기간 통계
    const [totalVisitors, pageViews, searchRequests] = await Promise.all([
      collection.distinct("ip", dateFilter).then((ips) => ips.length),
      collection.countDocuments(dateFilter),
      collection.countDocuments({ ...dateFilter, type: "search_start" }),
    ])

    // 이전 기간 통계 (변화율 계산용)
    const previousFilter = {
      ts: { $gte: previousStart, $lt: previousEnd },
    }
    const [prevVisitors, prevPageViews, prevSearchRequests] = await Promise.all([
      collection.distinct("ip", previousFilter).then((ips) => ips.length),
      collection.countDocuments(previousFilter),
      collection.countDocuments({ ...previousFilter, type: "search_start" }),
    ])

    // 변화율 계산
    const calcChange = (current: number, previous: number) => {
      if (previous === 0) return current > 0 ? 100 : 0
      return Number((((current - previous) / previous) * 100).toFixed(1))
    }

    return NextResponse.json({
      totalVisitors,
      pageViews,
      searchRequests,
      avgSessionTime: "4분 32초", // 실제 세션 추적이 필요한 경우 별도 로직 필요
      visitorChange: calcChange(totalVisitors, prevVisitors),
      pageViewChange: calcChange(pageViews, prevPageViews),
      searchChange: calcChange(searchRequests, prevSearchRequests),
      sessionChange: 0,
    })
  } catch (error) {
    console.error("Stats API Error:", error)
    return NextResponse.json({ error: "Failed to fetch stats" }, { status: 500 })
  }
}
