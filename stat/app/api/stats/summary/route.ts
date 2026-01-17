import { NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

export async function GET() {
  try {
    const db = await getDatabase()
    const logs = db.collection("logs")

    const now = new Date()
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const weekStart = new Date(todayStart)
    weekStart.setDate(weekStart.getDate() - 7)

    const [totalEvents, uniqueIPs, typeBreakdown, methodBreakdown, todayEvents, weekEvents] = await Promise.all([
      logs.countDocuments(),
      logs.distinct("ip").then((ips) => ips.length),
      logs
        .aggregate([
          { $group: { _id: "$type", count: { $sum: 1 } } },
          { $project: { type: "$_id", count: 1, _id: 0 } },
          { $sort: { count: -1 } },
        ])
        .toArray(),
      logs
        .aggregate([
          { $group: { _id: "$method", count: { $sum: 1 } } },
          { $project: { method: "$_id", count: 1, _id: 0 } },
          { $sort: { count: -1 } },
        ])
        .toArray(),
      logs.countDocuments({ timestamp: { $gte: todayStart } }),
      logs.countDocuments({ timestamp: { $gte: weekStart } }),
    ])

    return NextResponse.json({
      totalEvents,
      uniqueIPs,
      typeBreakdown,
      methodBreakdown,
      todayEvents,
      weekEvents,
    })
  } catch (error) {
    console.error("Summary stats error:", error)
    return NextResponse.json({ error: "Failed to fetch summary stats" }, { status: 500 })
  }
}
