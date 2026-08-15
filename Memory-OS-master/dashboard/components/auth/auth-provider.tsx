"use client";

import { useEffect } from "react";
import { auth } from "@/lib/api/client";

/** Restore access token from httpOnly refresh cookie on mount. */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    void auth.bootstrap();
  }, []);
  return <>{children}</>;
}
