import { Separator } from "@/components/ui/separator";
import { DashboardNav } from "@/components/layout/dashboard-nav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-border flex flex-col py-6 px-4 gap-6">
        <div className="px-2">
          <span className="text-lg font-bold tracking-tight text-foreground">OpenMontage</span>
          <p className="text-xs text-muted-foreground mt-0.5">AI 视频生产平台</p>
        </div>
        <Separator />
        <DashboardNav />
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
