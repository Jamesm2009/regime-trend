import { NextResponse } from "next/server";

const KEY_PREFIX = "rt_";

async function getJson(key: string) {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) {
    throw new Error("Upstash env vars not set");
  }
  const res = await fetch(`${url}/get/${KEY_PREFIX}${key}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const data = await res.json();
  if (!data.result) return null;
  return JSON.parse(data.result);
}

export async function GET() {
  try {
    const [modelParams, history, vtt] = await Promise.all([
      getJson("model_params"),
      getJson("history"),
      getJson("vtt_current"),
    ]);

    if (!modelParams || !history) {
      return NextResponse.json(
        { error: "No data yet — has weekly_refit.py run on the droplet?" },
        { status: 404 }
      );
    }

    return NextResponse.json({ modelParams, history, vtt });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
