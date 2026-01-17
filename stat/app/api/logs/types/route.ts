import { type NextRequest, NextResponse } from "next/server";
import { getDatabase } from "@/lib/mongodb";

const TYPE_LABELS: Record<string, string> = {
  homepage: "홈페이지 방문",
  search_start: "검색 시작",
  search_complete: "검색 완료",
  api_call: "API 호출",
};

export async function GET(request: NextRequest) {
  try {
    const db = await getDatabase();
    const collection = db.collection("logs");

    const searchParams = request.nextUrl.searchParams;
    const startDate = searchParams.get("startDate");
    const endDate = searchParams.get("endDate");

    // 날짜 필터 구성
    const matchStage: Record<string, unknown> = {};
    if (startDate || endDate) {
      matchStage.ts = {};
      if (startDate)
        (matchStage.ts as Record<string, unknown>).$gte = new Date(startDate);
      if (endDate)
        (matchStage.ts as Record<string, unknown>).$lte = new Date(endDate);
    }

    // 타입별 집계
    const typeData = await collection
      .aggregate([
        { $match: Object.keys(matchStage).length > 0 ? matchStage : {} },
        {
          $group: {
            _id: "$type",
            count: { $sum: 1 },
          },
        },
        { $sort: { count: -1 } },
      ])
      .toArray();

    return NextResponse.json(
      typeData.map((item) => ({
        name: item._id,
        value: item.count,
        label: TYPE_LABELS[item._id] || item._id,
      })),
    );
  } catch (error) {
    console.error("Types API Error:", error);
    return NextResponse.json(
      { error: "Failed to fetch type data" },
      { status: 500 },
    );
  }
}
