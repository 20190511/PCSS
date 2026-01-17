import { type NextRequest, NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const days = Number.parseInt(searchParams.get("days") || "30")

    const db = await getDatabase()
    const logs = db.collection("logs")

    const startDate = new Date()
    startDate.setDate(startDate.getDate() - days)
    startDate.setHours(0, 0, 0, 0)

    const timeseries = await logs
      .aggregate([
        { $match: { timestamp: { $gte: startDate } } },
        {
          $group: {
            _id: {
              date: {
                $dateToString: { format: "%Y-%m-%d", date: "$timestamp" },
              },
              type: "$type",
            },
            count: { $sum: 1 },
          },
        },
        {
          $group: {
            _id: "$_id.date",
            total: { $sum: "$count" },
            types: {
              $push: { type: "$_id.type", count: "$count" },
            },
          },
        },
        { $sort: { _id: 1 } },
      ])
      .toArray()

    const result = timeseries.map((item) => {
      const typeMap: Record<string, number> = {}
      item.types.forEach((t: { type: string; count: number }) => {
        typeMap[t.type] = t.count
      })
      return {
        date: item._id,
        count: item.total,
        pageViews: typeMap["page_view"] || 0,
        searches: typeMap["search"] || 0,
        detailViews: typeMap["detail_view"] || 0,
        apiCalls: typeMap["api_call"] || 0,
      }
    })

    return NextResponse.json(result)
  } catch (error) {
    console.error("Timeseries error:", error)
    return NextResponse.json({ error: "Failed to fetch timeseries" }, { status: 500 })
  }
}
