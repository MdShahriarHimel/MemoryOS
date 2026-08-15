import { NextRequest, NextResponse } from "next/server";
import { apiBaseUrl, cookieOptions, REFRESH_COOKIE } from "@/lib/auth/cookies";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${apiBaseUrl()}/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) return NextResponse.json(data, { status: res.status });

  const response = NextResponse.json({
    access_token: data.access_token,
    expires_in: data.expires_in,
  });
  response.cookies.set(REFRESH_COOKIE, data.refresh_token, cookieOptions());
  return response;
}
