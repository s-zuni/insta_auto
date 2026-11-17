"use client";

import { useEffect, useState } from "react";
import PreviewEditor from "@/components/PreviewEditor";
import TopicStyleSelector, { type Selection } from "@/components/TopicStyleSelector";
import { APP_MODE, generate, getHealth, publish, videoSrc } from "@/lib/agentClient";
import { CHANNELS, INDUSTRIES } from "@/lib/presets";
import type { AgentHealth, Channel, GenerateResponse, PublishResult } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  ok: "✅ 발행 완료", dry_run: "🧪 검증 통과(Dry-run)", failed: "❌ 실패", skipped: "⏭️ 건너뜀",
};

export default function Home() {
  const [sel, setSel] = useState<Selection>({
    industryId: INDUSTRIES[0].id, topic: INDUSTRIES[0].topics[0], style: "info", brandName: "", extra: "",
  });
  const [gen, setGen] = useState<GenerateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [channels, setChannels] = useState<Channel[]>(["instagram", "youtube", "threads", "naver_blog"]);
  const [dryRun, setDryRun] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [results, setResults] = useState<PublishResult[]>([]);
  const [health, setHealth] = useState<AgentHealth | null>(null);

  useEffect(() => { getHealth().then(setHealth); }, []);
  const agentDown = APP_MODE === "local" && !health;

  async function onGenerate() {
    setLoading(true); setError(null); setResults([]);
    try {
      const industry = INDUSTRIES.find((i) => i.id === sel.industryId)!;
      setGen(await generate({
        business_type: industry.label, topic: sel.topic, style: sel.style,
        brand_name: sel.brandName, extra_context: sel.extra, render_video: true,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "알 수 없는 오류");
    } finally { setLoading(false); }
  }

  async function onPublish() {
    if (!gen) return;
    if (!dryRun && !confirm("선택한 채널에 실제로 발행합니다. 계속할까요?")) return;
    setPublishing(true); setError(null);
    try {
      const res = await publish({ job_id: gen.job_id, channels, content: gen.content, dry_run: dryRun });
      setResults(res.results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "발행 중 오류");
    } finally { setPublishing(false); }
  }

  const toggle = (c: Channel) =>
    setChannels((p) => (p.includes(c) ? p.filter((x) => x !== c) : [...p, c]));

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-extrabold">올인원 AI 마케팅 자동화</h1>
          <p className="text-sm text-slate-500">주제와 스타일만 고르면 숏폼·쓰레드·블로그를 한 번에.</p>
        </div>
        <div className="flex gap-2 text-xs">
          <span className={`rounded-full px-3 py-1 font-semibold ${APP_MODE === "demo" ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>
            {APP_MODE === "demo" ? "데모 모드" : "로컬 모드"}
          </span>
          {health && (
            <span className="rounded-full bg-slate-200 px-3 py-1">
              AI {health.ai_configured ? "연결" : "Mock"} · FFmpeg {health.ffmpeg ? "OK" : "없음"}
            </span>
          )}
        </div>
      </header>

      {agentDown && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          로컬 에이전트에 연결할 수 없습니다. <code>scripts/start_local</code> 로 실행했는지 확인해 주세요.
        </div>
      )}
      {health?.license === "invalid" && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          라이선스 오류: {health.license_message}
        </div>
      )}

      <TopicStyleSelector value={sel} onChange={setSel} onSubmit={onGenerate} loading={loading} />

      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      {gen && (
        <>
          {gen.warnings.map((w) => (
            <div key={w} className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{w}</div>
          ))}
          <PreviewEditor content={gen.content} videoSrc={videoSrc(gen.video_url)} onChange={(content) => setGen({ ...gen, content })} />

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-lg font-bold">3. 원클릭 발행</h2>
            <div className="mb-3 flex flex-wrap gap-3">
              {CHANNELS.map((c) => (
                <label key={c.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={channels.includes(c.id)} onChange={() => toggle(c.id)} />
                  {c.label}
                  {health && !health.configured_channels[c.id] && <span className="text-xs text-red-500">(키 미설정)</span>}
                </label>
              ))}
            </div>
            <label className="mb-4 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
              Dry-run (검증만 하고 실제 업로드는 하지 않음)
            </label>
            <button
              onClick={onPublish}
              disabled={publishing || channels.length === 0}
              className={`w-full rounded-xl py-3 font-bold text-white disabled:opacity-50 ${dryRun ? "bg-slate-700 hover:bg-slate-800" : "bg-rose-600 hover:bg-rose-700"}`}
            >
              {publishing ? "처리 중…" : dryRun ? "🧪 검증 실행" : "🚀 4대 채널에 실제 발행"}
            </button>
            {results.length > 0 && (
              <ul className="mt-4 space-y-2 text-sm">
                {results.map((r) => (
                  <li key={r.channel} className="rounded-lg bg-slate-50 p-3">
                    <b>{CHANNELS.find((c) => c.id === r.channel)?.label}</b> — {STATUS_LABEL[r.status]}
                    <div className="text-slate-500">{r.message}</div>
                    {r.url && <a href={r.url} target="_blank" rel="noreferrer" className="text-brand underline">{r.url}</a>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  );
}
