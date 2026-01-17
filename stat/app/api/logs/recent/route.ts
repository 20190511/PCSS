import { type NextRequest, NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

export async function GET(request: NextRequest) {
  try {
    const db = await getDatabase()
    const collection = db.collection("access_logs")

    const searchParams = request.nextUrl.searchParams
    const startDate = searchParams.get("startDate")
    const endDate = searchParams.get("endDate")
    const type = searchParams.get("type")
    const page = Number.parseInt(searchParams.get("page") || "1")
    const limit = Number.parseInt(searchParams.get("limit") || "10")

    // 필터 구성
    const filter: Record<string, unknown> = {}
    if (startDate || endDate) {
      filter.ts = {}
      if (startDate) (filter.ts as Record<string, unknown>).$gte = new Date(startDate)
      if (endDate) (filter.ts as Record<string, unknown>).$lte = new Date(endDate)
    }
    if (type && type !== "all") {
      filter.type = type
    }

    const [logs, totalCount] = await Promise.all([
      collection
        .find(filter)
        .sort({ ts: -1 })
        .skip((page - 1) * limit)
        .limit(limit)
        .toArray(),
      collection.countDocuments(filter),
    ])

    return NextResponse.json({
      logs: logs.map((log) => ({
        id: log._id.toString(),
        ts: log.ts,
        type: log.type,
        ip: log.ip,
        method: log.method,
        path: log.path,
        user_agent: log.user_agent,
      })),
      totalCount,
      totalPages: Math.ceil(totalCount / limit),
      currentPage: page,
    })
  } catch (error) {
    console.error("Recent API Error:", error)
    return NextResponse.json({ error: "Failed to fetch recent logs" }, { status: 500 })
  }
}
