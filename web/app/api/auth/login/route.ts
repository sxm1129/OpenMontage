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
  //
  // `secure` must reflect the ACTUAL scheme of this request, not NODE_ENV —
  // confirmed live: a plain-HTTP docker-compose deployment (NODE_ENV=
  // production, no TLS-terminating reverse proxy) set Secure on the cookie,
  // which every browser silently drops on a non-HTTPS response. Login
  // returned {ok:true} but the session cookie never persisted, so the very
  // next navigation bounced back to /login with no visible error — "can't
  // log in" was actually "logged in every time, cookie discarded every
  // time". req.nextUrl.protocol reflects the raw connection scheme since
  // this deployment has no upstream proxy rewriting it.
  cookieStore.set(SESSION_COOKIE, sessionTokenFor(expected), {
    httpOnly: true,
    secure: req.nextUrl.protocol === "https:",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 7, // 7 days
    path: "/",
  });

  return NextResponse.json({ ok: true });
}
