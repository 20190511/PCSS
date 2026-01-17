import { type NextRequest, NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const ip = searchParams.get("ip")
    const limit = Number.parseInt(searchParams.get("limit") || "50")

    const db = await getDatabase()
    const logs = db.collection("logs")

    const query = ip ? { ip } : {}

    const recentLogs = await logs.find(query).sort({ timestamp: -1 }).limit(limit).toArray()

    return NextResponse.json(recentLogs)
  } catch (error) {
    console.error("Recent logs error:", error)
    return NextResponse.json({ error: "Failed to fetch recent logs" }, { status: 500 })
  }
}
