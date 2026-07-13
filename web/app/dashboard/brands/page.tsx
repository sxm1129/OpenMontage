"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
// Note: load()/handleSave()/handleDelete() below deliberately keep raw fetch
// rather than lib/api's apiRequest — their control flow relies on a network
// failure THROWING so it propagates to the enclosing try/catch (e.g. a failed
// post-save reload must hit handleSave's catch and keep the form open with
// its error visible, not fall through to the "close the form" success path).
// apiRequest never throws, so only the reference-image uploads — which branch
// on ok explicitly — use it.
import { SERVER, apiRequest } from "@/lib/api";

type BrandKit = {
  kit_id: string;
  brand_name: string;
  slogan: string;
  industry: string;
  tone_keywords: string[];
  color_palette: string[];
  target_audience: string;
  logo_url: string;
  style_notes: string;
  reference_image_path?: string;
  updated_at: number;
};

export default function BrandsPage() {
  const [kits, setKits] = useState<BrandKit[]>([]);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<BrandKit | null>(null);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);
  const [refImageFile, setRefImageFile] = useState<File | null>(null);
  const [refImagePreview, setRefImagePreview] = useState<string | null>(null);
  // The backend always writes a re-uploaded reference image to the same
  // fixed relative path, so a fresh upload returns a byte-identical URL to
  // the one already in state — the <img> never re-fetches. Bumping this on
  // every successful upload gives the <img src> a query param that changes
  // even when the underlying path doesn't.
  const [refImageVersion, setRefImageVersion] = useState(0);
  const [uploadingRefImage, setUploadingRefImage] = useState(false);
  const [refImageError, setRefImageError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  function emptyForm() {
    return {
      brand_name: "", slogan: "", industry: "",
      tone_keywords: "", color_palette: "", target_audience: "",
      logo_url: "", style_notes: "",
    };
  }

  async function load() {
    const res = await fetch(`${SERVER}/brands`);
    if (res.ok) setKits((await res.json()).brand_kits ?? []);
  }

  // Async fetch: setState happens after await, not synchronously in the effect.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, []);

  function startCreate() {
    setForm(emptyForm());
    setEditing(null);
    setCreating(true);
    setRefImageFile(null);
    setRefImagePreview(null);
    setRefImageVersion(0);
    setRefImageError(null);
    setSaveError(null);
  }

  function startEdit(kit: BrandKit) {
    setForm({
      brand_name: kit.brand_name,
      slogan: kit.slogan,
      industry: kit.industry,
      tone_keywords: kit.tone_keywords.join(", "),
      color_palette: kit.color_palette.join(", "),
      target_audience: kit.target_audience,
      logo_url: kit.logo_url,
      style_notes: kit.style_notes,
    });
    setEditing(kit);
    setCreating(true);
    setRefImageFile(null);
    setRefImagePreview(kit.reference_image_path ? `${SERVER}/brand-media/${kit.kit_id}/${kit.reference_image_path}` : null);
    setRefImageVersion(0);
    setRefImageError(null);
    setSaveError(null);
  }

  async function handleUploadReferenceImage() {
    if (!editing || !refImageFile) return;
    setUploadingRefImage(true);
    setRefImageError(null);
    const body = new FormData();
    body.append("file", refImageFile);
    const res = await apiRequest(`/brands/${editing.kit_id}/reference-image`, {
      method: "POST",
      body,
    });
    if (!res.ok) {
      setRefImageError("上传失败，请重试");
    } else {
      setRefImagePreview(`${SERVER}${res.data.reference_image_url}`);
      setRefImageVersion((v) => v + 1);
      setRefImageFile(null);
    }
    setUploadingRefImage(false);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    const payload = {
      ...form,
      tone_keywords: form.tone_keywords.split(",").map((s) => s.trim()).filter(Boolean),
      color_palette: form.color_palette.split(",").map((s) => s.trim()).filter(Boolean),
    };
    try {
      if (editing) {
        await fetch(`${SERVER}/brands/${editing.kit_id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        const createRes = await fetch(`${SERVER}/brands`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (createRes.ok && refImageFile) {
          // Immediately follow up with the reference-image upload so the
          // whole thing reads as one atomic "create brand kit with
          // reference image" action to the user, instead of two separate
          // steps they'd otherwise have to discover (create, then re-open
          // to attach an image).
          const newKit: BrandKit = await createRes.json();
          const uploadBody = new FormData();
          uploadBody.append("file", refImageFile);
          // apiRequest never throws — a network failure comes back as
          // ok: false, exactly the uploadOk = false this used to hand-roll
          // with an inner try/catch.
          const uploadRes = await apiRequest(`/brands/${newKit.kit_id}/reference-image`, {
            method: "POST",
            body: uploadBody,
          });
          if (!uploadRes.ok) {
            // The kit itself was created successfully — don't roll that
            // back or silently swallow the follow-up failure. Drop into
            // edit mode for the new kit so the error stays visible and a
            // retry (via the now-available upload button, or a plain
            // re-save) acts on the existing kit instead of creating a
            // duplicate.
            setSaveError("品牌 Kit 已创建，但参考图上传失败，请重试上传");
            setEditing(newKit);
            await load();
            return;
          }
        }
      }
      await load();
      setCreating(false);
      setEditing(null);
    } catch {
      setSaveError("保存失败，请检查网络连接后重试");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(kit_id: string) {
    if (!confirm("确定删除？")) return;
    setListError(null);
    try {
      await fetch(`${SERVER}/brands/${kit_id}`, { method: "DELETE" });
      await load();
    } catch {
      setListError("删除失败，请检查网络连接后重试");
    }
  }

  return (
    <div className="p-8 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">品牌库</h1>
          <p className="text-muted-foreground text-sm mt-1">保存品牌资产，AI 自动引用生成风格一致的视频</p>
        </div>
        {!creating && (
          <Button onClick={startCreate}>+ 新建品牌 Kit</Button>
        )}
      </div>

      {/* Create / Edit form */}
      {creating && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{editing ? "编辑品牌 Kit" : "新建品牌 Kit"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSave} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium block mb-1.5">品牌名称 *</label>
                  <Input required value={form.brand_name} onChange={(e) => setForm(f => ({ ...f, brand_name: e.target.value }))} placeholder="小狗牌咖啡机" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5">行业</label>
                  <Input value={form.industry} onChange={(e) => setForm(f => ({ ...f, industry: e.target.value }))} placeholder="消费电子 / 快消 / 科技…" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium block mb-1.5">Slogan</label>
                  <Input value={form.slogan} onChange={(e) => setForm(f => ({ ...f, slogan: e.target.value }))} placeholder="好咖啡，不只属于咖啡馆" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5">Logo URL</label>
                  <Input value={form.logo_url} onChange={(e) => setForm(f => ({ ...f, logo_url: e.target.value }))} placeholder="https://…/logo.png" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium block mb-1.5">情感关键词（逗号分隔）</label>
                  <Input value={form.tone_keywords} onChange={(e) => setForm(f => ({ ...f, tone_keywords: e.target.value }))} placeholder="温暖, 仪式感, 品质" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5">品牌色彩（Hex，逗号分隔）</label>
                  <Input value={form.color_palette} onChange={(e) => setForm(f => ({ ...f, color_palette: e.target.value }))} placeholder="#1A1A1A, #C8A96E, #F5F0E8" />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium block mb-1.5">目标受众</label>
                <Input value={form.target_audience} onChange={(e) => setForm(f => ({ ...f, target_audience: e.target.value }))} placeholder="25-40 岁都市白领，注重生活品质" />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1.5">风格备注</label>
                <Textarea rows={2} value={form.style_notes} onChange={(e) => setForm(f => ({ ...f, style_notes: e.target.value }))} placeholder="慢镜头、暖调、微距特写、无旁白…" />
              </div>
              {/* Rendered in both create and edit mode now — the upload
                endpoint needs an existing kit_id, so in create mode the
                manual "上传参考图" button (which calls
                handleUploadReferenceImage, requiring `editing`) is swapped
                for a hint that the file will be attached automatically once
                the kit is saved; see the create branch of handleSave. */}
              <div>
                <label className="text-sm font-medium block mb-1.5">参考图</label>
                <div className="flex items-center gap-3">
                  {refImagePreview && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={refImageVersion > 0 ? `${refImagePreview}?t=${refImageVersion}` : refImagePreview}
                      alt="参考图预览"
                      className="w-24 h-24 object-cover rounded border border-border"
                    />
                  )}
                  <div className="flex flex-col gap-2 items-start">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => setRefImageFile(e.target.files?.[0] ?? null)}
                      className="text-xs"
                    />
                    {editing ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={!refImageFile || uploadingRefImage}
                        onClick={handleUploadReferenceImage}
                      >
                        {uploadingRefImage ? "上传中…" : "上传参考图"}
                      </Button>
                    ) : (
                      refImageFile && (
                        <p className="text-xs text-muted-foreground">将在保存品牌 Kit 时自动上传</p>
                      )
                    )}
                    {refImageError && <p className="text-xs text-destructive">{refImageError}</p>}
                  </div>
                </div>
              </div>
              {saveError && <p className="text-xs text-destructive">{saveError}</p>}
              <div className="flex gap-3 pt-2">
                <Button type="submit" disabled={saving}>{saving ? "保存中…" : "保存"}</Button>
                <Button type="button" variant="outline" onClick={() => { setCreating(false); setEditing(null); }}>取消</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {listError && <p className="text-xs text-destructive">{listError}</p>}

      {/* Kit list */}
      {kits.length === 0 && !creating && (
        <div className="flex flex-col items-center justify-center h-48 border border-dashed border-border rounded-lg gap-3">
          <p className="text-muted-foreground text-sm">还没有品牌 Kit</p>
          <Button variant="outline" onClick={startCreate}>创建第一个</Button>
        </div>
      )}

      <div className="space-y-3">
        {kits.map((kit) => (
          <Card key={kit.kit_id} className="hover:border-foreground/20 transition-colors">
            <CardContent className="pt-4 pb-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-sm">{kit.brand_name}</h3>
                    {kit.industry && (
                      <span className="text-xs text-muted-foreground border border-border rounded px-1.5 py-0.5">{kit.industry}</span>
                    )}
                  </div>
                  {kit.slogan && (
                    <p className="text-xs text-muted-foreground mt-0.5 italic">&ldquo;{kit.slogan}&rdquo;</p>
                  )}
                  <div className="flex gap-3 mt-2 flex-wrap items-center">
                    {kit.tone_keywords.slice(0, 4).map((k) => (
                      <span key={k} className="text-xs bg-muted px-2 py-0.5 rounded-full">{k}</span>
                    ))}
                    {kit.tone_keywords.length > 4 && (
                      <span className="text-xs text-muted-foreground">+{kit.tone_keywords.length - 4}</span>
                    )}
                    {kit.color_palette.slice(0, 4).map((c) => (
                      <span
                        key={c}
                        className="w-4 h-4 rounded-full border border-border inline-block"
                        style={{ backgroundColor: c }}
                        title={c}
                      />
                    ))}
                    {kit.color_palette.length > 4 && (
                      <span
                        className="text-xs text-muted-foreground"
                        title={`还有 ${kit.color_palette.length - 4} 个颜色`}
                      >
                        +{kit.color_palette.length - 4}
                      </span>
                    )}
                  </div>
                  {kit.target_audience && (
                    <p className="text-xs text-muted-foreground mt-1.5">受众：{kit.target_audience}</p>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button size="sm" variant="outline" onClick={() => startEdit(kit)}>编辑</Button>
                  <Button size="sm" variant="outline" className="text-destructive border-destructive/40 hover:bg-destructive/10" onClick={() => handleDelete(kit.kit_id)}>删除</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
