import type {
  AgentHealth, GenerateRequest, GenerateResponse, PublishRequest, PublishResponse,
} from "./types";

export const APP_MODE: "demo" | "local" =
  process.env.NEXT_PUBLIC_APP_MODE === "local" ? "local" : "demo";
export const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://127.0.0.1:8787";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ---------- Demo Mock (Vercel 시연용: 실제 영상/업로드 없음) ----------
function mockGenerate(req: GenerateRequest): GenerateResponse {
  const hook = `${req.topic}, 아직도 모르세요?`;
  const points = [
    `${req.business_type} 사장님이 직접 알려주는 ${req.topic} 핵심`,
    "현장에서 바로 써먹을 수 있는 방법만 골랐어요",
    "저장해두고 필요할 때 꺼내 보세요",
  ];
  return {
    job_id: `demo-${Date.now()}`,
    video_url: null,
    mock: true,
    warnings: ["데모 모드: 샘플 콘텐츠이며 영상 생성·실제 업로드는 로컬 패키지에서 동작합니다."],
    content: {
      shorts: {
        title: hook,
        scenes: [hook, ...points, "더 궁금하면 문의 주세요"].map((n, i) => ({
          narration: n, on_screen_text: i === 0 ? hook : `POINT ${i}`, image_prompt: "",
        })),
        caption: `${hook}\n저장 필수!`,
        hashtags: [req.business_type, "소상공인", "사장님꿀팁"],
        video_path: null,
        duration_sec: null,
      },
      threads: { posts: [hook, ...points.map((p, i) => `${i + 1}. ${p}`), "궁금한 건 댓글로 물어봐줘"] },
      blog: {
        title: `${req.topic} | ${req.business_type} 사장님이 알려주는 핵심 정리`,
        body_markdown: `# ${req.topic}\n\n${hook}\n\n## 먼저 결론부터\n${points.map((p) => `- ${p}`).join("\n")}\n\n## 마무리\n문의는 언제든 편하게 주세요.`,
        tags: [req.business_type, req.topic.replace(/\s/g, ""), "소상공인"],
        meta_description: `${req.topic} 핵심을 ${req.business_type} 사장님이 정리했어요.`,
      },
    },
  };
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${AGENT_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Agent 오류 (${res.status})`);
  }
  return res.json() as Promise<T>;
}

// ---------- Public API ----------
export async function getHealth(): Promise<AgentHealth | null> {
  if (APP_MODE === "demo") return null;
  try {
    return await http<AgentHealth>("/health");
  } catch {
    return null; // Agent 미기동
  }
}

export async function generate(req: GenerateRequest): Promise<GenerateResponse> {
  if (APP_MODE === "demo") {
    await sleep(900);
    return mockGenerate(req);
  }
  return http<GenerateResponse>("/api/generate", { method: "POST", body: JSON.stringify(req) });
}

export async function publish(req: PublishRequest): Promise<PublishResponse> {
  if (APP_MODE === "demo") {
    await sleep(700);
    return {
      job_id: req.job_id,
      results: req.channels.map((channel) => ({
        channel, status: "dry_run" as const, url: null,
        message: "데모 모드 — 실제 업로드는 하지 않았습니다.",
      })),
    };
  }
  return http<PublishResponse>("/api/publish", { method: "POST", body: JSON.stringify(req) });
}

export const videoSrc = (videoUrl: string | null) => (videoUrl ? `${AGENT_URL}${videoUrl}` : null);
