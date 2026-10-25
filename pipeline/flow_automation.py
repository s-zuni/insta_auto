"""
Google Gemini Flow (labs.google/fx/ko/tools/flow) Browser Automation & Free Video Source Engine.

지원 모드 (비용 최소화 우선순위):
1. Google Gemini Flow 브라우저 자동화 (Playwright / CDP):
   - 구글 실험실 Flow 웹(https://labs.google/fx/ko/tools/flow)에 로그인된 크롬 프로필로 접속해
     API 종량제 과금($0.35~$0.50/초) 없이 웹 크레딧으로 고화질 Veo 영상 및 Imagen 이미지를 자동 생성·추출합니다.
   - 최초 1회: `python -m pipeline.flow_automation --login` 으로 구글 로그인 세션 저장.
   - 이후 자동 실행: `USE_GOOGLE_FLOW=true` 설정 시 씬별 프롬프트 입력 및 규격별 넘버링 다운로드.
2. Pexels / Pixabay 무료 고화질 영상 API 폴백 (비용 0원, 서버 무인 가동 100% 호환):
   - 로컬 브라우저를 띄울 수 없는 클라우드(Railway 등) 환경이거나 Flow 비활성화 시,
     `PEXELS_API_KEY` 또는 `PIXABAY_API_KEY`(무료 발급)로 씬 분위기에 맞는 실사 HD 영상을 다운로드합니다.
3. Google GenAI / Vertex AI Veo API 직접 호출 (선택):
   - `USE_VEO_API=true` 설정 시 공식 Veo API를 통해 MP4 영상을 생성합니다.
"""
import os
import re
import sys
import time
import json
import requests
from pathlib import Path
from typing import Optional, List, Dict
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FLOW_URL = os.getenv("GOOGLE_FLOW_URL", "https://flow.google.com/")
DEFAULT_PROFILE_DIR = PROJECT_ROOT / "assets" / "chrome_flow_profile"

# 한국어/영문 프롬프트에서 무료 스톡 영상 검색어로 변환할 때 제외할 메타 단어
_STOPWORDS = {
    "horizontal", "16:9", "landscape", "ratio", "candid", "smartphone", "photo",
    "taken", "real", "person", "authentic", "natural", "available", "light",
    "realistic", "skin", "texture", "pores", "slight", "imperfections", "ordinary",
    "look", "film", "grain", "shallow", "depth", "field", "studio", "shot",
    "cgi", "render", "illustration", "airbrushed", "face", "text", "letters",
    "watermark", "logo", "clean", "composition", "cinematic", "photorealistic",
    "late", "early", "mid", "20s", "30s", "her", "his", "with", "from", "into",
}


def extract_video_search_query(visual_prompt: str, fallback: str = "korean woman cafe") -> str:
    """
    긴 AI 이미지 프롬프트에서 Pexels/Pixabay 검색에 적합한 핵심 키워드 3~4개를 추출합니다.
    """
    words = re.findall(r"[a-zA-Z]+", (visual_prompt or "").lower())
    filtered = [w for w in words if len(w) > 2 and w not in _STOPWORDS]
    if not filtered:
        return fallback
    # 상위 핵심 명사/행동 4개 조합
    query = " ".join(filtered[:4])
    return query


def fetch_pexels_video(prompt: str, output_path: Path, min_duration: int = 3) -> bool:
    """
    Pexels Video API (100% 무료)를 사용해 씬 프롬프트 분위기에 맞는 16:9 HD 영상을 다운로드합니다.
    환경변수: PEXELS_API_KEY (https://www.pexels.com/api/ 에서 무료 발급)
    """
    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_"):
        return False

    query = extract_video_search_query(prompt)
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": "portrait",
        "size": "medium",
        "per_page": 8,
    }

    try:
        print(f"    [PEXELS-VIDEO] 무료 HD 스톡 영상 검색 중 (query='{query}')...")
        resp = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=20)
        if resp.status_code != 200:
            return False
        data = resp.json()
        videos = data.get("videos") or []
        if not videos and query != "korean cafe lifestyle":
            # 검색 결과가 없으면 범용 감성 키워드로 재검색
            params["query"] = "korean cafe lifestyle"
            resp = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=20)
            videos = (resp.json().get("videos") or []) if resp.status_code == 200 else []

        for vid in videos:
            dur = int(vid.get("duration", 0))
            if dur < min_duration:
                continue
            files = vid.get("video_files") or []
            # 1280x720 ~ 1920x1080 MP4 우선 선택 (메모리 절약 및 빠른 렌더링)
            mp4_files = [
                f for f in files
                if "mp4" in str(f.get("file_type", "")).lower()
                and 640 <= int(f.get("width") or 0) <= 1920
            ]
            if not mp4_files:
                mp4_files = [f for f in files if f.get("link")]
            if not mp4_files:
                continue

            mp4_files.sort(key=lambda f: abs(int(f.get("width") or 1280) - 1280))
            download_url = mp4_files[0].get("link")
            if not download_url:
                continue

            r_vid = requests.get(download_url, timeout=45)
            if r_vid.status_code == 200 and len(r_vid.content) > 50_000:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(r_vid.content)
                print(f"    [PEXELS-VIDEO] ✅ 영상 다운로드 완료 -> {output_path.name} ({len(r_vid.content) // 1024}KB)")
                return True
    except Exception as e:
        print(f"    [WARN] Pexels 영상 검색 실패: {e}")

    return False


def fetch_pixabay_video(prompt: str, output_path: Path) -> bool:
    """
    Pixabay Video API (100% 무료)를 사용해 씬 프롬프트 분위기에 맞는 HD 영상을 다운로드합니다.
    환경변수: PIXABAY_API_KEY (https://pixabay.com/api/docs/ 에서 무료 발급)
    """
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_"):
        return False

    query = extract_video_search_query(prompt, fallback="coffee cafe")
    params = {
        "key": api_key,
        "q": query,
        "video_type": "film",
        "per_page": 8,
    }
    try:
        print(f"    [PIXABAY-VIDEO] 무료 HD 스톡 영상 검색 중 (query='{query}')...")
        resp = requests.get("https://pixabay.com/api/videos/", params=params, timeout=20)
        if resp.status_code != 200:
            return False
        hits = resp.json().get("hits") or []
        for hit in hits:
            videos = hit.get("videos") or {}
            medium = videos.get("medium") or videos.get("small") or videos.get("large") or {}
            url = medium.get("url")
            if not url:
                continue
            r_vid = requests.get(url, timeout=45)
            if r_vid.status_code == 200 and len(r_vid.content) > 50_000:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(r_vid.content)
                print(f"    [PIXABAY-VIDEO] ✅ 영상 다운로드 완료 -> {output_path.name}")
                return True
    except Exception as e:
        print(f"    [WARN] Pixabay 영상 검색 실패: {e}")
    return False


def _launch_persistent_browser(p, profile_dir: Path, headless: bool = False):
    """
    구글 계정 로그인 보안에 가장 안전한 브라우저(1순위: Chrome, 2순위: Edge, 3순위: Chromium)로
    영구 세션 컨텍스트를 실행합니다.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    channels_to_try = ["chrome", "msedge", None]
    last_err = None

    for ch in channels_to_try:
        try:
            kwargs = {
                "user_data_dir": str(profile_dir),
                "headless": headless,
                "accept_downloads": True,
                "viewport": {"width": 1440, "height": 900},
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            }
            if ch:
                kwargs["channel"] = ch
            return p.chromium.launch_persistent_context(**kwargs)
        except Exception as e:
            last_err = e
            continue

    # 폴백: 기본 chromium
    return p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=headless,
        accept_downloads=True,
    )


def generate_with_google_flow_browser(
    prompt: str,
    output_path: Path,
    asset_type: str = "video",
    timeout_sec: int = 150,
) -> bool:
    """
    Playwright를 통해 구글 제미나이 Flow (https://flow.google.com / https://labs.google/fx/ko/tools/flow)에 접속하여
    주제/장면에 맞는 고화질 Veo 영상 또는 Imagen 이미지 소스를 자동 생성 후 다운로드합니다.
    """
    use_flow = os.getenv("USE_GOOGLE_FLOW", "").strip().lower() in ("1", "true", "yes")
    if not use_flow:
        return False

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("    [FLOW][INFO] playwright 패키지가 설치되지 않아 브라우저 자동화를 건너뜁니다. (pip install playwright)")
        return False

    cdp_url = os.getenv("FLOW_CDP_URL", "").strip()
    profile_dir = Path(os.getenv("FLOW_USER_DATA_DIR", str(DEFAULT_PROFILE_DIR)))
    headless = os.getenv("FLOW_HEADLESS", "true").strip().lower() in ("1", "true", "yes")

    clean_prompt = (
        f"Vertical 9:16 portrait smartphone video: {prompt.strip()}. "
        f"Candid realistic Korean everyday scene, natural lighting, "
        f"9:16 vertical full-screen mobile framing, centered subject, subtle natural motion, no text, no watermark."
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"    [GOOGLE-FLOW] 🌐 제미나이 Flow 접속 및 {asset_type.upper()} 에셋 자동 생성 시작...")
    try:
        with sync_playwright() as p:
            if cdp_url:
                browser = p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0] if browser.contexts else browser.new_context(accept_downloads=True)
                page = context.new_page()
            else:
                context = _launch_persistent_browser(p, profile_dir, headless=headless)
                page = context.pages[0] if context.pages else context.new_page()

            page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=35_000)
            page.wait_for_timeout(3000)

            # 1. 쿠키/이용약관 동의 팝업 처리
            agree_btn = page.locator("button:has-text('동의함'), button:has-text('I agree')")
            if agree_btn.count() > 0 and agree_btn.first.is_visible():
                try:
                    agree_btn.first.click()
                    page.wait_for_timeout(500)
                except Exception:
                    pass

            # 2. 프로젝트 진입 (이미 프로젝트가 아니면 기존 프로젝트 클릭 또는 새 프로젝트 생성)
            if "project" not in page.url:
                proj_card = page.locator("a[href*='/project/'], div[data-project-id]").first
                if proj_card.count() > 0 and proj_card.is_visible():
                    try:
                        proj_card.click()
                        page.wait_for_timeout(4000)
                    except Exception:
                        pass

                if "project" not in page.url:
                    new_proj_btn = page.locator("button:has-text('새 프로젝트'), button:has-text('New project')").first
                    if new_proj_btn.count() > 0 and new_proj_btn.is_visible():
                        try:
                            new_proj_btn.click()
                            page.wait_for_timeout(4000)
                        except Exception:
                            pass

            # 3. 스튜디오 프롬프트 입력창 탐색
            prompt_selectors = [
                "[contenteditable='true']",
                "textarea[placeholder*='프롬프트']",
                "textarea[placeholder*='설명']",
                "textarea[placeholder*='Prompt']",
                "textarea",
            ]
            input_box = None
            for sel in prompt_selectors:
                loc = page.locator(sel).last
                if loc.count() > 0 and loc.is_visible():
                    input_box = loc
                    break

            if input_box is None:
                print("    [GOOGLE-FLOW][WARN] 프롬프트 입력창을 찾지 못했습니다. 로그인 상태를 확인하세요.")
                context.close()
                return False

            input_box.click()
            input_box.fill(clean_prompt)
            page.wait_for_timeout(800)

            # 4. 생성 요청 제출 (우하단 화살표 버튼 또는 Enter)
            submit_btn = page.locator("button[aria-label*='생성'], button:has(svg), button:has-text('생성')").last
            if submit_btn.count() > 0 and submit_btn.is_visible():
                try:
                    submit_btn.click()
                except Exception:
                    input_box.press("Enter")
            else:
                input_box.press("Enter")

            # 5. 크레딧 차감 확인 팝업 (예: "15 크레딧을 사용하여 1개 동영상 생성을 시작하시겠습니까?")
            page.wait_for_timeout(3000)
            approve_btn = None
            for approve_text in ["항상 승인", "승인", "Always approve", "Approve"]:
                candidate = page.get_by_text(approve_text, exact=False).first
                try:
                    if candidate.count() > 0 and candidate.is_visible():
                        approve_btn = candidate
                        break
                except Exception:
                    continue

            if approve_btn is not None:
                try:
                    print("    [GOOGLE-FLOW] 💳 크레딧 승인 버튼 감지 및 자동 승인 클릭...")
                    approve_btn.click(timeout=3000)
                    page.wait_for_timeout(2000)
                except Exception as ex_app:
                    print(f"    [GOOGLE-FLOW] 승인 버튼 클릭 스킵(이미 승인됨): {ex_app}")

            print(f"    [GOOGLE-FLOW] ⏳ Veo 영상 생성 렌더링 대기 중 (최대 {timeout_sec}초)...")
            start_wait = time.time()
            # 비디오 생성 완료 대기 (보통 45초~80초 소요)
            page.wait_for_timeout(35000)

            downloaded = False
            while time.time() - start_wait < timeout_sec:
                # 캔버스 중앙 비디오 카드 선택
                try:
                    page.mouse.click(320, 220)
                    page.wait_for_timeout(1500)
                except Exception:
                    pass

                # 하단 컨트롤 바의 미디어 다운로드 버튼 탐색
                dl_btn = page.locator("button[aria-label='미디어 다운로드'], button[aria-label*='다운로드'], button:has-text('download')").first
                if dl_btn.count() > 0 and dl_btn.is_visible():
                    try:
                        dl_btn.click()
                        page.wait_for_timeout(1000)

                        # 해상도 메뉴에서 720p 옵션 탐색
                        opt_720 = page.locator("text='720p'").first
                        if opt_720.count() > 0 and opt_720.is_visible():
                            print("    [GOOGLE-FLOW] 📥 720p MP4 다운로드 트리거...")
                            with page.expect_download(timeout=60_000) as dl_info:
                                opt_720.click()
                            dl = dl_info.value
                            dl.save_as(str(output_path))
                            if output_path.is_file() and output_path.stat().st_size > 30_000:
                                downloaded = True
                                break
                    except Exception as ex_dl:
                        print(f"    [GOOGLE-FLOW] 다운로드 대기 중 ({ex_dl})...")

                page.wait_for_timeout(6000)

            context.close()
            if downloaded:
                print(f"    [GOOGLE-FLOW] ✅ Veo 영상 다운로드 완료 -> {output_path.name} ({output_path.stat().st_size // 1024} KB)")
                return True
    except Exception as e:
        print(f"    [GOOGLE-FLOW][WARN] 브라우저 자동화 예외 발생: {e}")

    return False


def generate_with_veo_api(prompt: str, output_path: Path) -> bool:
    """
    Google GenAI SDK를 통해 공식 Veo 모델(veo-2.0-generate-001)로 16:9 비디오를 생성합니다.
    (비용 보호를 위해 USE_VEO_API=true 가 명시된 경우에만 호출합니다.)
    """
    if os.getenv("USE_VEO_API", "").strip().lower() not in ("1", "true", "yes"):
        return False

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_"):
        return False

    try:
        from google import genai
        from google.genai import types

        model_name = os.getenv("VEO_MODEL", "veo-2.0-generate-001")
        print(f"    [VEO-API] 🎬 Veo({model_name}) 영상 생성 요청 중...")
        client = genai.Client(api_key=api_key)
        operation = client.models.generate_videos(
            model=model_name,
            prompt=f"{prompt}. Authentic Korean everyday scene, natural daylight, 9:16 vertical portrait, no text.",
            config=types.GenerateVideosConfig(
                aspect_ratio="9:16",
                number_of_videos=1,
            ),
        )
        while not operation.done:
            time.sleep(6)
            operation = client.operations.get(operation)

        if operation.response and operation.response.generated_videos:
            video_obj = operation.response.generated_videos[0]
            client.files.download(file=video_obj.video)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            video_obj.video.save(str(output_path))
            if output_path.is_file() and output_path.stat().st_size > 20_000:
                print(f"    [VEO-API] ✅ Veo 영상 생성 완료 -> {output_path.name}")
                return True
    except Exception as e:
        print(f"    [VEO-API][WARN] Veo 영상 생성 실패: {e}")
    return False


def acquire_scene_video(
    scene_id: int,
    prompt: str,
    output_dir: Path,
) -> Optional[Path]:
    """
    하이브리드 영상 소스 수집기 (비용 최소화 우선순위):
    1순위: Google Gemini Flow 브라우저 자동화 (`USE_GOOGLE_FLOW=true`)
    2순위: Pexels 무료 HD 스톡 영상 API (`PEXELS_API_KEY`)
    3순위: Pixabay 무료 HD 스톡 영상 API (`PIXABAY_API_KEY`)
    4순위: Google Veo 공식 API (`USE_VEO_API=true` 명시 시)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = output_dir / f"scene_{scene_id:02d}_raw.mp4"

    # 이미 로컬에 사전 추출된 Flow 영상이 있는 경우 재사용 (FLOW_REUSE_EXISTING=true)
    if os.getenv("FLOW_REUSE_EXISTING", "").strip().lower() in ("1", "true", "yes") and video_path.is_file():
        if video_path.stat().st_size > 30_000:
            print(f"    [VIDEO-SOURCE] ♻️ 사전 생성된 영상 소스 재사용 -> {video_path.name}")
            return video_path

    if generate_with_google_flow_browser(prompt, video_path, asset_type="video"):
        return video_path

    if fetch_pexels_video(prompt, video_path):
        return video_path

    if fetch_pixabay_video(prompt, video_path):
        return video_path

    if generate_with_veo_api(prompt, video_path):
        return video_path

    return None


def launch_flow_login_session():
    """
    최초 1회 구글 제미나이 Flow 로그인 세션을 저장하기 위한 대화형 브라우저 실행기.
    """
    from playwright.sync_api import sync_playwright

    profile_dir = Path(os.getenv("FLOW_USER_DATA_DIR", str(DEFAULT_PROFILE_DIR)))
    profile_dir.mkdir(parents=True, exist_ok=True)
    print(f"[GOOGLE-FLOW] 🌐 로그인 세션 저장용 크롬을 실행합니다: {profile_dir}")
    print(f"[GOOGLE-FLOW] 열릴 브라우저에서 Google 계정으로 로그인하고 Flow({FLOW_URL}) 화면이 보이면 창을 닫으세요.")

    with sync_playwright() as p:
        context = _launch_persistent_browser(p, profile_dir, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(FLOW_URL)
        try:
            page.wait_for_event("close", timeout=600_000)
        except Exception:
            pass
        context.close()
    print("[GOOGLE-FLOW] ✅ 로그인 프로필 저장이 완료되었습니다!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Google Gemini Flow & Free Video Source Automation CLI")
    parser.add_argument("--login", action="store_true", help="구글 제미나이 Flow 로그인 세션 저장용 브라우저 실행")
    parser.add_argument("--prompt", type=str, default="", help="테스트할 씬 비주얼 프롬프트")
    parser.add_argument("--scene-id", type=int, default=1, help="씬 번호 (기본: 1)")
    parser.add_argument("--out-dir", type=str, default="assets/videos", help="저장 폴더")
    args = parser.parse_args()

    if args.login:
        launch_flow_login_session()
    elif args.prompt:
        res = acquire_scene_video(args.scene_id, args.prompt, Path(args.out_dir))
        if res:
            print(f"[SUCCESS] 영상 에셋 확보 완료: {res}")
        else:
            print("[INFO] 사용 가능한 영상 소스가 없습니다 (USE_GOOGLE_FLOW 또는 PEXELS_API_KEY 설정 확인).")
    else:
        parser.print_help()

