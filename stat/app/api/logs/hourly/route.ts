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
    const matchStage: Record<string, unknown> = {}
    if (startDate || endDate) {
      matchStage.ts = {}
      if (startDate) (matchStage.ts as Record<string, unknown>).$gte = new Date(startDate)
      if (endDate) (matchStage.ts as Record<string, unknown>).$lte = new Date(endDate)
    }

    // 시간대별 집계
    const hourlyData = await collection
      .aggregate([
        { $match: Object.keys(matchStage).length > 0 ? matchStage : {} },
        {
          $group: {
            _id: { $hour: { $toDate: "$ts" } },
            requests: { $sum: 1 },
          },
        },
        { $sort: { _id: 1 } },
      ])
      .toArray()

    // 0-23시 전체 데이터로 변환
    const hourMap = new Map(hourlyData.map((item) => [item._id, item.requests]))
    const fullHourlyData = Array.from({ length: 24 }, (_, i) => ({
      hour: `${i.toString().padStart(2, "0")}시`,
      requests: hourMap.get(i) || 0,
    }))

    return NextResponse.json(fullHourlyData)
  } catch (error) {
    console.error("Hourly API Error:", error)
    return NextResponse.json({ error: "Failed to fetch hourly data" }, { status: 500 })
  }
}
