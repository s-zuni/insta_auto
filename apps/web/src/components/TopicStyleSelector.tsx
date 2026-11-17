"use client";

import { INDUSTRIES, STYLES } from "@/lib/presets";
import type { StyleId } from "@/lib/types";

export interface Selection {
  industryId: string;
  topic: string;
  style: StyleId;
  brandName: string;
  extra: string;
}

interface Props {
  value: Selection;
  onChange: (v: Selection) => void;
  onSubmit: () => void;
  loading: boolean;
}

export default function TopicStyleSelector({ value, onChange, onSubmit, loading }: Props) {
  const industry = INDUSTRIES.find((i) => i.id === value.industryId) ?? INDUSTRIES[0];
  const set = (patch: Partial<Selection>) => onChange({ ...value, ...patch });

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 text-lg font-bold">1. 무엇을, 어떤 느낌으로 만들까요?</h2>

      <p className="mb-2 text-sm font-semibold text-slate-600">업종</p>
      <div className="mb-4 flex flex-wrap gap-2">
        {INDUSTRIES.map((i) => (
          <button
            key={i.id}
            onClick={() => set({ industryId: i.id, topic: i.topics[0] })}
            className={`rounded-full border px-4 py-1.5 text-sm transition ${
              i.id === industry.id ? "border-brand bg-brand text-white" : "border-slate-300 hover:border-brand"
            }`}
          >
            {i.label}
          </button>
        ))}
      </div>

      <p className="mb-2 text-sm font-semibold text-slate-600">마케팅 주제 (추천 선택 또는 직접 입력)</p>
      <div className="mb-2 flex flex-wrap gap-2">
        {industry.topics.map((t) => (
          <button
            key={t}
            onClick={() => set({ topic: t })}
            className={`rounded-lg border px-3 py-1.5 text-sm ${
              t === value.topic ? "border-brand bg-brand-soft text-brand-dark" : "border-slate-200 hover:border-brand"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      <input
        value={value.topic}
        onChange={(e) => set({ topic: e.target.value })}
        placeholder="예: 여름 시즌 신메뉴 소개"
        className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
      />

      <p className="mb-2 text-sm font-semibold text-slate-600">콘텐츠 스타일</p>
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {STYLES.map((s) => (
          <button
            key={s.id}
            onClick={() => set({ style: s.id })}
            className={`rounded-xl border p-3 text-left transition ${
              s.id === value.style ? "border-brand bg-brand-soft" : "border-slate-200 hover:border-brand"
            }`}
          >
            <div className="text-xl">{s.emoji}</div>
            <div className="text-sm font-bold">{s.label}</div>
            <div className="text-xs text-slate-500">{s.desc}</div>
          </button>
        ))}
      </div>

      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        <input
          value={value.brandName}
          onChange={(e) => set({ brandName: e.target.value })}
          placeholder="가게 이름 (선택)"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
        />
        <input
          value={value.extra}
          onChange={(e) => set({ extra: e.target.value })}
          placeholder="덧붙일 정보: 가격·위치·이벤트 (선택)"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
        />
      </div>

      <button
        onClick={onSubmit}
        disabled={loading || value.topic.trim().length < 2}
        className="w-full rounded-xl bg-brand py-3 font-bold text-white transition hover:bg-brand-dark disabled:opacity-50"
      >
        {loading ? "AI가 3종 콘텐츠를 만드는 중…" : "✨ 3종 콘텐츠 한 번에 만들기"}
      </button>
    </section>
  );
}
