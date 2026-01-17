import { NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

export async function GET() {
  try {
    const db = await getDatabase()
    const logs = db.collection("logs")

    const hourlyData = await logs
      .aggregate([
        {
          $group: {
            _id: { $hour: "$timestamp" },
            count: { $sum: 1 },
          },
        },
        { $project: { hour: "$_id", count: 1, _id: 0 } },
        { $sort: { hour: 1 } },
      ])
      .toArray()

    // Fill in missing hours with 0
    const hourMap = new Map(hourlyData.map((h) => [h.hour, h.count]))
    const result = Array.from({ length: 24 }, (_, i) => ({
      hour: i,
      count: hourMap.get(i) || 0,
    }))

    return NextResponse.json(result)
  } catch (error) {
    console.error("Hourly stats error:", error)
    return NextResponse.json({ error: "Failed to fetch hourly stats" }, { status: 500 })
  }
}
