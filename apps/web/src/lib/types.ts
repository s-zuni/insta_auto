/**
 * Agent(FastAPI) 와 주고받는 표준 타입.
 * ⚠️ `apps/agent/core/schemas.py` 와 1:1 대응. 한쪽을 바꾸면 반드시 같이 수정할 것.
 */
export type StyleId = "info" | "story" | "review" | "promo" | "empathy";
export type Channel = "instagram" | "youtube" | "threads" | "naver_blog";
export type PublishStatus = "ok" | "failed" | "dry_run" | "skipped";

export interface GenerateRequest {
  business_type: string;
  topic: string;
  style: StyleId;
  brand_name?: string;
  extra_context?: string;
  render_video?: boolean;
}

export interface Scene {
  narration: string;
  on_screen_text: string;
  image_prompt: string;
}

export interface ShortsContent {
  title: string;
  scenes: Scene[];
  caption: string;
  hashtags: string[];
  video_path: string | null;
  duration_sec: number | null;
}

export interface ThreadsContent {
  posts: string[];
}

export interface BlogContent {
  title: string;
  body_markdown: string;
  tags: string[];
  meta_description: string;
}

export interface GeneratedContent {
  shorts: ShortsContent;
  threads: ThreadsContent;
  blog: BlogContent;
}

export interface GenerateResponse {
  job_id: string;
  content: GeneratedContent;
  video_url: string | null;
  warnings: string[];
  mock: boolean;
}

export interface PublishRequest {
  job_id: string;
  channels: Channel[];
  content: GeneratedContent;
  dry_run: boolean;
}

export interface PublishResult {
  channel: Channel;
  status: PublishStatus;
  url: string | null;
  message: string;
}

export interface PublishResponse {
  job_id: string;
  results: PublishResult[];
}

export interface AgentHealth {
  status: "ok";
  app_mode: string;
  version: string;
  ffmpeg: boolean;
  ai_configured: boolean;
  license: "valid" | "invalid" | "not_required";
  license_message: string;
  configured_channels: Record<Channel, boolean>;
}
