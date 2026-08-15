export const REFRESH_COOKIE = "mos_refresh";

export function apiBaseUrl(): string {
  return (
    process.env.MEMORY_OS_API_URL ??
    process.env.NEXT_PUBLIC_MEMORY_OS_API_URL ??
    "http://localhost:8000"
  );
}

export function cookieOptions(maxAge = 60 * 60 * 24 * 14) {
  return {
    httpOnly: true as const,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}
