"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge, stageLabel } from "@/components/job-status";
import { CONTENT_TYPES } from "@/lib/pipeline-picker";
import { apiRequest } from "@/lib/api";

type Job = {
  job_id: string;
  project_name: string;
  content_type: string;
  status: string;
  current_stage: string | null;
  created_at: number;
  brand_info?: { brand_name?: string };
};

// Derived from the wizard's CONTENT_TYPES so this list can never drift out of
// sync with it again — this page used to hardcode its own copy, which lacked
// the "demo" and "short" entries, so those jobs showed raw ids. Unknown ids
// still fall back to the raw content_type at the lookup site below.
const CONTENT_TYPE_LABEL: Record<string, string> = Object.fromEntries(
  CONTENT_TYPES.map((ct) => [ct.id, ct.label])
);

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  async function fetchJobs() {
    const res = await apiRequest("/jobs");
    if (res.ok) setJobs(res.data.jobs ?? []);
    setLoading(false);
  }

  useEffect(() => {
    // Async fetch: setState happens after await, not synchronously in the effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchJobs();
    // Poll every 8s so status badges update
    const id = setInterval(fetchJobs, 8000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">我的项目</h1>
          <p className="text-muted-foreground text-sm mt-1">AI 驱动的视频生产任务</p>
        </div>
        <Link href="/dashboard/new">
          <Button>+ 新建视频</Button>
        </Link>
      </div>

      {loading && (
        <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">加载中…</div>
      )}

      {!loading && jobs.length === 0 && (
        <div className="flex flex-col items-center justify-center h-64 border border-dashed border-border rounded-lg gap-4">
          <p className="text-muted-foreground text-sm">还没有项目</p>
          <Link href="/dashboard/new">
            <Button variant="outline">创建第一个视频</Button>
          </Link>
        </div>
      )}

      {!loading && jobs.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {jobs.map((job) => {
            const displayName = job.project_name || job.brand_info?.brand_name || job.job_id;
            const contentLabel = CONTENT_TYPE_LABEL[job.content_type] ?? job.content_type;
            const date = new Date(job.created_at * 1000).toLocaleDateString("zh-CN");
            return (
              <Link key={job.job_id} href={`/dashboard/jobs/${job.job_id}`}>
                <Card className="hover:border-foreground/30 transition-colors cursor-pointer h-full">
                  <div className="aspect-video bg-muted rounded-t-lg flex items-center justify-center relative overflow-hidden">
                    {job.status === "running" && (
                      <div className="absolute inset-0 flex items-center justify-center gap-1">
                        {[0, 1, 2].map((i) => (
                          <span
                            key={i}
                            className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce"
                            style={{ animationDelay: `${i * 0.15}s` }}
                          />
                        ))}
                      </div>
                    )}
                    <span className="text-muted-foreground/40 text-xs">
                      {job.status === "completed" ? "🎬" : stageLabel(job.current_stage)}
                    </span>
                  </div>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-base leading-tight">{displayName}</CardTitle>
                      {/* Shared badge from job-status.tsx — this page used to
                          hardcode a near-identical STATUS_META map that lacked
                          "cancelled", so a cancelled job fell back to the
                          "排队中" (queued) badge here while its own detail
                          page correctly showed "已取消". The shrink-0 wrapper
                          keeps the badge from collapsing next to a long
                          project title, as the old inline span did. */}
                      <span className="shrink-0">
                        <StatusBadge status={job.status} />
                      </span>
                    </div>
                    <CardDescription className="text-xs">{contentLabel}</CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-xs text-muted-foreground">{date}</p>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
