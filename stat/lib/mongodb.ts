import { MongoClient, type Db } from "mongodb"

if (!process.env.MONGODB_URI) {
  throw new Error("MONGODB_URI 환경변수가 설정되지 않았습니다.")
}

const uri = process.env.MONGODB_URI
const options = {}

let client: MongoClient
let clientPromise: Promise<MongoClient>

declare global {
  var _mongoClientPromise: Promise<MongoClient> | undefined
}

if (process.env.NODE_ENV === "development") {
  if (!global._mongoClientPromise) {
    client = new MongoClient(uri, options)
    global._mongoClientPromise = client.connect()
  }
  clientPromise = global._mongoClientPromise
} else {
  client = new MongoClient(uri, options)
  clientPromise = client.connect()
}

export async function getDatabase(): Promise<Db> {
  const client = await clientPromise
  return client.db("pcss")
}

export default clientPromise

async function printAllLogsToTerminal() {
  try {
    const db = await getDatabase()
    const logs = await db.collection("logs").find({}).toArray()

    console.log("\n========== [PCSS] logs collection dump ==========")
    console.log("count =", logs.length)
    console.log(
      logs.map((d) => ({
        ...d,
        _id: d._id?.toString?.() ?? d._id,
        ts: d.ts instanceof Date ? d.ts.toISOString() : d.ts,
      }))
    )
    console.log("========== [PCSS] end ==========\n")
  } catch (e) {
    console.error("[PCSS] Failed to dump logs:", e)
  }
}

printAllLogsToTerminal()
