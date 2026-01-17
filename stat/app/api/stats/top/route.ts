import { type NextRequest, NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const field = searchParams.get("field") || "path"
    const limit = Number.parseInt(searchParams.get("limit") || "10")

    const db = await getDatabase()
    const logs = db.collection("logs")

    const validFields = ["path", "ip", "user_agent", "referrer"]
    if (!validFields.includes(field)) {
      return NextResponse.json({ error: "Invalid field" }, { status: 400 })
    }

    const matchStage =
      field === "referrer" ? { $match: { referrer: { $exists: true, $ne: "", $ne: null } } } : { $match: {} }

    const top = await logs
      .aggregate([
        matchStage,
        { $group: { _id: `$${field}`, count: { $sum: 1 } } },
        { $project: { value: "$_id", count: 1, _id: 0 } },
        { $sort: { count: -1 } },
        { $limit: limit },
      ])
      .toArray()

    return NextResponse.json(top)
  } catch (error) {
    console.error("Top stats error:", error)
    return NextResponse.json({ error: "Failed to fetch top stats" }, { status: 500 })
  }
}
