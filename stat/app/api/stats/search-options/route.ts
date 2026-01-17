import { NextResponse } from "next/server"
import { getDatabase } from "@/lib/mongodb"

export async function GET() {
  try {
    const db = await getDatabase()
    const logs = db.collection("logs")

    const searchLogs = { type: "search", search_options: { $exists: true } }

    const [totalSearches, avgUncertaintyResult, conferenceDistribution, yearRangeDistribution, uncertaintyHistogram] =
      await Promise.all([
        logs.countDocuments(searchLogs),
        logs
          .aggregate([
            { $match: { ...searchLogs, "search_options.uncertainty": { $exists: true } } },
            { $group: { _id: null, avg: { $avg: "$search_options.uncertainty" } } },
          ])
          .toArray(),
        logs
          .aggregate([
            { $match: { ...searchLogs, "search_options.conferences": { $exists: true } } },
            { $unwind: "$search_options.conferences" },
            { $group: { _id: "$search_options.conferences", count: { $sum: 1 } } },
            { $project: { conference: "$_id", count: 1, _id: 0 } },
            { $sort: { count: -1 } },
            { $limit: 15 },
          ])
          .toArray(),
        logs
          .aggregate([
            {
              $match: {
                ...searchLogs,
                "search_options.year_start": { $exists: true },
                "search_options.year_end": { $exists: true },
              },
            },
            {
              $project: {
                range: {
                  $subtract: ["$search_options.year_end", "$search_options.year_start"],
                },
              },
            },
            {
              $bucket: {
                groupBy: "$range",
                boundaries: [0, 1, 3, 5, 10, 20, 100],
                default: "Other",
                output: { count: { $sum: 1 } },
              },
            },
          ])
          .toArray(),
        logs
          .aggregate([
            { $match: { ...searchLogs, "search_options.uncertainty": { $exists: true } } },
            {
              $bucket: {
                groupBy: "$search_options.uncertainty",
                boundaries: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                default: "1.0+",
                output: { count: { $sum: 1 } },
              },
            },
          ])
          .toArray(),
      ])

    const rangeLabels: Record<number | string, string> = {
      0: "같은 해",
      1: "1-2년",
      3: "3-4년",
      5: "5-9년",
      10: "10-19년",
      20: "20년+",
      Other: "기타",
    }

    return NextResponse.json({
      totalSearches,
      avgUncertainty: avgUncertaintyResult[0]?.avg || 0,
      conferenceDistribution,
      yearRangeDistribution: yearRangeDistribution.map((item) => ({
        range: rangeLabels[item._id] || item._id,
        count: item.count,
      })),
      uncertaintyHistogram: uncertaintyHistogram.map((item) => ({
        range: typeof item._id === "number" ? `${item._id.toFixed(1)}-${(item._id + 0.1).toFixed(1)}` : item._id,
        count: item.count,
      })),
    })
  } catch (error) {
    console.error("Search options error:", error)
    return NextResponse.json({ error: "Failed to fetch search options stats" }, { status: 500 })
  }
}
