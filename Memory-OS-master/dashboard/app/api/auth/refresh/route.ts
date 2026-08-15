import { NextRequest, NextResponse } from "next/server";
import { apiBaseUrl, cookieOptions, REFRESH_COOKIE } from "@/lib/auth/cookies";

export async function POST(req: NextRequest) {
  const refresh = req.cookies.get(REFRESH_COOKIE)?.value;
  if (!refresh) {
    return NextResponse.json(
      { error: { code: "UNAUTHENTICATED", message: "No session." } },
      { status: 401 },
    );
  }

  const res = await fetch(`${apiBaseUrl()}/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
    cache: "no-store",
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const response = NextResponse.json(data, { status: res.status });
    response.cookies.delete(REFRESH_COOKIE);
    return response;
  }

  const response = NextResponse.json({
    access_token: data.access_token,
    expires_in: data.expires_in,
  });
  response.cookies.set(REFRESH_COOKIE, data.refresh_token, cookieOptions());
  return response;
}
