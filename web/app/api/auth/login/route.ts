import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { SESSION_COOKIE, configuredPassphrase, safeEqual, sessionTokenFor } from "@/lib/session";

export async function POST(req: NextRequest) {
  let passphrase: unknown;
  try {
    ({ passphrase } = await req.json());
  } catch {
    // A malformed body is a client error, not a 500.
    return NextResponse.json({ error: "Malformed request body" }, { status: 400 });
  }

  const expected = configuredPassphrase();
  if (!expected || typeof passphrase !== "string" || !safeEqual(passphrase, expected)) {
    return NextResponse.json({ error: "Invalid passphrase" }, { status: 401 });
  }

  const cookieStore = await cookies();
  // HMAC-derived token (see lib/session.ts) — verified by proxy.ts AND by the
  // FastAPI backend's auth middleware, replacing the forgeable constant
  // "authenticated" value.
  cookieStore.set(SESSION_COOKIE, sessionTokenFor(expected), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 7, // 7 days
    path: "/",
  });

  return NextResponse.json({ ok: true });
}
