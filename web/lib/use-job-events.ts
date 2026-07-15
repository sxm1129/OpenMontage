// EventSource lifecycle for the job detail page, extracted out of the page's
// useEffect. Its contract is deliberately narrow now that job-lifecycle.ts
// owns the state machine: parse each incoming SSE message and dispatch a
// single raw-event action, letting the reducer's switch do the per-type
// mapping. That keeps this hook a thin transport layer — connect, resume,
// backoff, terminal-event detection, cleanup — with none of the "what does
// this event mean" logic duplicated here.

import { useEffect, useRef } from "react";
import { SERVER } from "@/lib/api";
import type { SseEvent } from "@/components/job-status";
import type { JobLifecycleAction } from "@/lib/job-lifecycle";

// SSE reconnect backoff: starts at the base interval and doubles on each
// consecutive failure, capped at the max — a multi-minute backend outage
// with the tab left open would otherwise hammer the server with a fixed
// 2s retry forever. Reset back to the base the moment a connection
// actually succeeds (es.onopen), so a single blip doesn't leave the page
// slow to reconnect on the next, unrelated blip.
const SSE_RECONNECT_BASE_MS = 2000;
const SSE_RECONNECT_MAX_MS = 30000;

/**
 * Owns the job's EventSource connection and forwards every parsed message to
 * `dispatch` as a `{ type: "sse_event", event }` action. Returns a manual
 * `reconnect()` for callers that need to re-open the stream after an action
 * that resurrects a job the stream had already given up on (see the retry
 * button's use of it in the page).
 */
export function useJobEvents(jobId: string, dispatch: (action: JobLifecycleAction) => void) {
  const lastSeqRef = useRef(-1);
  const lastEventTypeRef = useRef<string | null>(null); // type of the most recently processed event
  const doneRef = useRef(false); // job reached a terminal state
  const connectRef = useRef<(() => EventSource | null) | null>(null);
  const esRef = useRef<EventSource | null>(null); // the currently live connection, if any
  const reconnectDelayRef = useRef(SSE_RECONNECT_BASE_MS); // current backoff wait, doubles per failed attempt

  useEffect(() => {
    // All of these refs are SHARED across effect runs of the same hook
    // instance, and the App Router re-renders the same [jobId] page component
    // when navigating job A → job B — the effect re-runs WITHOUT an unmount.
    // Each run therefore resets the per-job state: without this, job B
    // resumed from job A's lastEventId (skipping B's early events) and a
    // completed A left doneRef=true so B never reconnected after a blip.
    doneRef.current = false;
    lastSeqRef.current = -1;
    lastEventTypeRef.current = null;
    // Effect-generation flag: a backoff setTimeout captured by job A's
    // closure must not revive A's stream after the effect re-ran for job B.
    // A shared "cancelled" ref cannot express this — B's run resets it to
    // false, re-arming A's pending timer (audit 2026-07-15, BUG-10). Only a
    // per-generation local survives correctly.
    let cancelledThisGeneration = false;
    let pendingRetry: ReturnType<typeof setTimeout> | null = null;
    const connect = () => {
      if (cancelledThisGeneration) return null;
      // A manual reconnect (or an overlapping generation) may find a live
      // connection — close it before overwriting esRef, or it leaks and
      // keeps dispatching in the background.
      esRef.current?.close();
      const url = `${SERVER}/jobs/${jobId}/events?lastEventId=${lastSeqRef.current}`;
      // withCredentials: EventSource cannot set custom headers, so when the
      // backend enforces auth (OM_TEAM_PASSPHRASE set) the om_session cookie
      // is its only way in. No-op when auth is disabled.
      const es = new EventSource(url, { withCredentials: true });
      esRef.current = es;
      es.onopen = () => {
        // Connection actually succeeded — reset the backoff so a future,
        // unrelated blip starts retrying from the base interval again
        // instead of inheriting whatever delay this outage grew to.
        reconnectDelayRef.current = SSE_RECONNECT_BASE_MS;
      };
      es.onmessage = (e) => {
        const ev: SseEvent = JSON.parse(e.data);
        lastSeqRef.current = ev.seq;
        lastEventTypeRef.current = ev.type;
        dispatch({ type: "sse_event", event: ev });
      };
      es.onerror = () => {
        es.close();
        // A replay (or any reconnect spanning more than one retry cycle) can
        // contain an OLD job_failed from an earlier, since-superseded attempt
        // followed by many more events from a later retry that finished
        // differently (even a real job_completed) — see the matching comment
        // in server/app/routers/events.py. So don't treat job_failed/
        // job_completed as terminal at the moment they're seen; only stop
        // reconnecting once the connection actually ends on one of them,
        // which is exactly when the backend intentionally closed the stream.
        const endedOnTerminalEvent =
          lastEventTypeRef.current === "job_completed" ||
          lastEventTypeRef.current === "job_failed" ||
          lastEventTypeRef.current === "job_cancelled";
        if (endedOnTerminalEvent) {
          doneRef.current = true;
          return;
        }
        // Reconnect only while the job is live and this effect generation is
        // still current (the generation flag is never reset by a later
        // effect run — see above).
        if (!doneRef.current && !cancelledThisGeneration) {
          const delay = reconnectDelayRef.current;
          reconnectDelayRef.current = Math.min(delay * 2, SSE_RECONNECT_MAX_MS);
          pendingRetry = setTimeout(() => {
            if (!cancelledThisGeneration && !doneRef.current) connect();
          }, delay);
        }
      };
      return es;
    };
    connectRef.current = connect;
    connect();
    return () => {
      cancelledThisGeneration = true;
      if (pendingRetry) clearTimeout(pendingRetry);
      esRef.current?.close();
    };
  }, [jobId, dispatch]);

  /**
   * Manual reconnect for the retry button: the previous EventSource already
   * closed (the backend ended that stream once it drained to the earlier
   * terminal event) and nothing was scheduled to reconnect it, so open a
   * fresh one from where we left off rather than just flipping a flag
   * nothing reacts to.
   */
  function reconnect() {
    doneRef.current = false;
    connectRef.current?.();
  }

  return { reconnect };
}
