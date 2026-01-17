import { NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

export async function GET() {
  try {
    const db = await getDatabase()
    const logs = db.collection("logs")

    const [homeVisits, searches, detailViews] = await Promise.all([
      logs.countDocuments({
        $or: [
          { type: "page_view", path: "/" },
          { type: "page_view", path: { $regex: /^\/?$/ } },
        ],
      }),
      logs.countDocuments({ type: "search" }),
      logs.countDocuments({ type: "detail_view" }),
    ])

    return NextResponse.json({
      homeVisits: homeVisits || 1,
      searches,
      detailViews,
      homeToSearchRate: homeVisits > 0 ? (searches / homeVisits) * 100 : 0,
      searchToDetailRate: searches > 0 ? (detailViews / searches) * 100 : 0,
    })
  } catch (error) {
    console.error("Funnel error:", error)
    return NextResponse.json({ error: "Failed to fetch funnel data" }, { status: 500 })
  }
}
