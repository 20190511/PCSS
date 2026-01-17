import { NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

export async function GET() {
  try {
    const db = await getDatabase()
    const logs = db.collection("logs")

    const dailyData = await logs
      .aggregate([
        {
          $group: {
            _id: { $dayOfWeek: "$timestamp" },
            count: { $sum: 1 },
          },
        },
        { $project: { day: "$_id", count: 1, _id: 0 } },
        { $sort: { day: 1 } },
      ])
      .toArray()

    const dayNames = ["일", "월", "화", "수", "목", "금", "토"]
    const dayMap = new Map(dailyData.map((d) => [d.day, d.count]))
    const result = Array.from({ length: 7 }, (_, i) => ({
      day: dayNames[i],
      count: dayMap.get(i + 1) || 0,
    }))

    return NextResponse.json(result)
  } catch (error) {
    console.error("Daily stats error:", error)
    return NextResponse.json({ error: "Failed to fetch daily stats" }, { status: 500 })
  }
}
