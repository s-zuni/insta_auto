"use client";

import type { GeneratedContent } from "@/lib/types";

interface Props {
  content: GeneratedContent;
  videoSrc: string | null;
  onChange: (c: GeneratedContent) => void;
}

const box = "rounded-2xl border border-slate-200 bg-white p-4 shadow-sm";
const area =
  "w-full rounded-lg border border-slate-200 p-2 text-sm leading-relaxed focus:border-brand focus:outline-none";

/** 숏폼 / 쓰레드 / 네이버 블로그 3분할 검수·수정 에디터 */
export default function PreviewEditor({ content, videoSrc, onChange }: Props) {
  const { shorts, threads, blog } = content;

  return (
    <section>
      <h2 className="mb-3 text-lg font-bold">2. 검수하고 필요하면 고치세요</h2>
      <div className="grid gap-4 lg:grid-cols-3">
        {/* 숏폼 */}
        <div className={box}>
          <h3 className="mb-2 font-bold">🎬 숏폼 (릴스 · 쇼츠)</h3>
          {videoSrc ? (
            <video src={videoSrc} controls className="mx-auto mb-3 aspect-[9/16] max-h-[360px] rounded-lg bg-black" />
          ) : (
            <div className="mb-3 flex aspect-[9/16] max-h-[200px] items-center justify-center rounded-lg bg-slate-100 text-xs text-slate-500">
              영상 미리보기 없음 (데모 또는 렌더링 생략)
            </div>
          )}
          <label className="text-xs font-semibold text-slate-500">제목</label>
          <input
            className={`${area} mb-2`}
            value={shorts.title}
            onChange={(e) => onChange({ ...content, shorts: { ...shorts, title: e.target.value } })}
          />
          <label className="text-xs font-semibold text-slate-500">장면 대본 (영상은 발행 전 재생성 필요)</label>
          {shorts.scenes.map((s, i) => (
            <textarea
              key={i}
              rows={2}
              className={`${area} mb-1`}
              value={s.narration}
              onChange={(e) => {
                const scenes = shorts.scenes.map((x, j) => (j === i ? { ...x, narration: e.target.value } : x));
                onChange({ ...content, shorts: { ...shorts, scenes } });
              }}
            />
          ))}
          <label className="text-xs font-semibold text-slate-500">캡션</label>
          <textarea
            rows={3}
            className={area}
            value={shorts.caption}
            onChange={(e) => onChange({ ...content, shorts: { ...shorts, caption: e.target.value } })}
          />
        </div>

        {/* 쓰레드 */}
        <div className={box}>
          <h3 className="mb-2 font-bold">🧵 쓰레드 체인</h3>
          {threads.posts.map((p, i) => (
            <div key={i} className="mb-2">
              <textarea
                rows={3}
                className={area}
                value={p}
                onChange={(e) => {
                  const posts = threads.posts.map((x, j) => (j === i ? e.target.value : x));
                  onChange({ ...content, threads: { posts } });
                }}
              />
              <div className={`text-right text-xs ${p.length > 500 ? "text-red-600" : "text-slate-400"}`}>
                {i + 1}/{threads.posts.length} · {p.length}/500자
              </div>
            </div>
          ))}
        </div>

        {/* 블로그 */}
        <div className={box}>
          <h3 className="mb-2 font-bold">📝 네이버 블로그</h3>
          <input
            className={`${area} mb-2 font-semibold`}
            value={blog.title}
            onChange={(e) => onChange({ ...content, blog: { ...blog, title: e.target.value } })}
          />
          <textarea
            rows={16}
            className={area}
            value={blog.body_markdown}
            onChange={(e) => onChange({ ...content, blog: { ...blog, body_markdown: e.target.value } })}
          />
          <div className="text-right text-xs text-slate-400">{blog.body_markdown.length}자</div>
          <input
            className={`${area} mt-1`}
            value={blog.tags.join(", ")}
            onChange={(e) =>
              onChange({ ...content, blog: { ...blog, tags: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) } })
            }
            placeholder="태그 (쉼표 구분)"
          />
        </div>
      </div>
    </section>
  );
}
