import { NextRequest, NextResponse } from "next/server";
import { apiBaseUrl, cookieOptions, REFRESH_COOKIE } from "@/lib/auth/cookies";

async function proxyAuth(path: string, body: unknown) {
  const res = await fetch(`${apiBaseUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  return { res, data };
}

function sessionResponse(data: {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}) {
  const response = NextResponse.json({
    access_token: data.access_token,
    expires_in: data.expires_in,
  });
  response.cookies.set(REFRESH_COOKIE, data.refresh_token, cookieOptions());
  return response;
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { res, data } = await proxyAuth("/v1/auth/login", body);
  if (!res.ok) return NextResponse.json(data, { status: res.status });
  return sessionResponse(data);
}
