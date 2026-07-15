// Server-only session-token derivation, shared by the login route and
// proxy.ts. The token is HMAC-SHA256(key=passphrase, msg=fixed context) —
// exactly what the FastAPI backend's PassphraseAuth derives
// (server/app/interfaces/auth.py, _TOKEN_CONTEXT), so the cookie set at
// login is directly verifiable by BOTH the Next proxy and the backend's
// auth middleware without any shared state, and — unlike the previous
// constant "authenticated" cookie — unforgeable without the passphrase.

import { createHmac, timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE = "om_session";

// Must stay byte-identical to server/app/interfaces/auth.py's _TOKEN_CONTEXT.
const TOKEN_CONTEXT = "openmontage-session-v1";

/**
 * The configured team passphrase. OM_TEAM_PASSPHRASE is the single source of
 * truth (same variable the FastAPI backend reads); ACCESS_PASSPHRASE is kept
 * as a legacy fallback for existing .env files. Undefined → auth disabled
 * (local single-user mode, mirroring the backend's zero-config default).
 */
export function configuredPassphrase(): string | undefined {
  return process.env.OM_TEAM_PASSPHRASE || process.env.ACCESS_PASSPHRASE || undefined;
}

export function sessionTokenFor(passphrase: string): string {
  return createHmac("sha256", passphrase).update(TOKEN_CONTEXT).digest("hex");
}

/** The expected cookie value, or null when no passphrase is configured. */
export function expectedSessionToken(): string | null {
  const passphrase = configuredPassphrase();
  return passphrase ? sessionTokenFor(passphrase) : null;
}

/** Constant-time string comparison (length leak is fine — token length is public). */
export function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  return ab.length === bb.length && timingSafeEqual(ab, bb);
}
