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

    // 일별 집계
    const dailyData = await collection
      .aggregate([
        { $match: Object.keys(matchStage).length > 0 ? matchStage : {} },
        {
          $group: {
            _id: {
              $dateToString: { format: "%m/%d", date: { $toDate: "$ts" } },
            },
            pageviews: { $sum: 1 },
            uniqueIps: { $addToSet: "$ip" },
          },
        },
        {
          $project: {
            date: "$_id",
            pageviews: 1,
            visitors: { $size: "$uniqueIps" },
          },
        },
        { $sort: { date: 1 } },
        { $limit: 30 },
      ])
      .toArray()

    return NextResponse.json(
      dailyData.map((item) => ({
        date: item.date,
        visitors: item.visitors,
        pageviews: item.pageviews,
      })),
    )
  } catch (error) {
    console.error("Daily API Error:", error)
    return NextResponse.json({ error: "Failed to fetch daily data" }, { status: 500 })
  }
}
