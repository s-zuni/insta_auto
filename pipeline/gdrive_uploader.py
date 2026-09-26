"""
Google Drive Automatic Uploader Module for Instagram Reels Pipeline.
Uses OAuth user credentials (not a service account) to upload videos, captions, and
metadata, since service accounts have 0-byte storage quota on personal Gmail Drives.
Creates date-based subfolders and sets public read permissions for direct download.
"""
import os
import sys
import json
import datetime
from pathlib import Path
from typing import Optional, Dict, Any
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


DRIVE_OAUTH_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _load_oauth_credentials():
    """
    사용자(OAuth) 인증 정보로 Credentials 객체를 만듭니다.
    서비스 계정은 개인 Gmail 드라이브에서 저장 용량이 0바이트라 파일 업로드가 항상
    403 storageQuotaExceeded로 실패하기 때문에(2020년 구글 정책 변경), 반드시 실제
    사용자 계정으로 인증한 OAuth 자격 증명을 사용해야 합니다.

    자격 증명은 두 가지 방식 중 하나로 제공합니다:
    1) GOOGLE_OAUTH_TOKEN_JSON 환경 변수 (Railway 등 배포 환경에 권장) - 전체 토큰 JSON 문자열
    2) GOOGLE_OAUTH_TOKEN_PATH 환경 변수 또는 기본값 'token.json' 파일 (로컬 개발용)

    두 방식 모두 `pipeline/gdrive_oauth_setup.py`를 한 번 실행해서 생성합니다.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token_json = os.getenv("GOOGLE_OAUTH_TOKEN_JSON", "").strip()
    token_path = os.getenv("GOOGLE_OAUTH_TOKEN_PATH", "").strip() or str(PROJECT_ROOT / "token.json")

    if token_json:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info, scopes=DRIVE_OAUTH_SCOPES)
    elif os.path.isfile(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes=DRIVE_OAUTH_SCOPES)
    else:
        raise FileNotFoundError(
            "Google Drive OAuth 토큰을 찾을 수 없습니다. "
            "먼저 'python pipeline/gdrive_oauth_setup.py' 를 로컬에서 실행해 "
            "1회 로그인하고, 생성된 token.json 내용을 GOOGLE_OAUTH_TOKEN_JSON 환경 변수로 등록하세요."
        )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # 로컬 파일 모드일 때만 갱신된 토큰을 다시 저장합니다.
        if not token_json and os.path.isfile(token_path):
            Path(token_path).write_text(creds.to_json(), encoding="utf-8")

    return creds


def get_drive_service():
    """Google Drive API 서비스 객체를 사용자 OAuth 자격 증명으로 생성합니다."""
    from googleapiclient.discovery import build

    credentials = _load_oauth_credentials()
    return build("drive", "v3", credentials=credentials)


def find_or_create_folder(service, folder_name: str, parent_id: Optional[str] = None) -> str:
    """지정한 폴더를 검색하고, 없으면 새로 생성하여 folder_id를 반환합니다."""
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        clean_parent = parent_id.split("?")[0].strip()
        query += f" and '{clean_parent}' in parents"

    response = service.files().list(q=query, fields="files(id, name)").execute()
    files = response.get("files", [])

    if files:
        return files[0]["id"]

    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        file_metadata["parents"] = [parent_id.split("?")[0].strip()]

    folder = service.files().create(body=file_metadata, fields="id").execute()
    return folder.get("id")


def make_file_publicly_readable(service, file_id: str) -> bool:
    """파일 권한을 '링크가 있는 모든 사용자(reader)'로 설정합니다."""
    try:
        service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
            supportsAllDrives=True
        ).execute()
        return True
    except Exception as e:
        print(f"  [WARN] Drive 공개 읽기 권한 설정 중 알림: {e}")
        return False


def upload_file_to_drive(
    file_path: str | Path,
    folder_id: Optional[str] = None,
    mime_type: Optional[str] = None,
    make_public: bool = False
) -> Dict[str, str]:
    """
    단일 파일을 Google Drive에 업로드하고 직간접 다운로드 링크를 생성합니다.
    """
    from googleapiclient.http import MediaFileUpload

    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"업로드할 파일이 존재하지 않습니다: {file_path}")

    service = get_drive_service()

    if mime_type is None:
        if file_path.suffix == ".mp4":
            mime_type = "video/mp4"
        elif file_path.suffix == ".txt":
            mime_type = "text/plain"
        elif file_path.suffix == ".json":
            mime_type = "application/json"
        elif file_path.suffix in (".jpg", ".jpeg"):
            mime_type = "image/jpeg"
        else:
            mime_type = "application/octet-stream"

    file_metadata: Dict[str, Any] = {"name": file_path.name}
    if folder_id:
        file_metadata["parents"] = [folder_id.split("?")[0].strip()]

    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)
    uploaded_file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id, name, webViewLink, webContentLink", supportsAllDrives=True)
        .execute()
    )

    file_id = uploaded_file.get("id", "")
    web_link = uploaded_file.get("webViewLink", "")

    direct_download_url = ""
    if file_id:
        if make_public:
            make_file_publicly_readable(service, file_id)
        # Instagram Graph API 등이 직접 영상을 다운로드할 수 있는 직링크 형식
        direct_download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    return {
        "id": file_id,
        "name": uploaded_file.get("name", ""),
        "link": web_link,
        "direct_url": direct_download_url,
    }


def upload_reels_assets_to_drive(
    video_path: str | Path,
    caption_path: Optional[str | Path] = None,
    metadata_path: Optional[str | Path] = None,
    custom_folder_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    릴스 생성물(비디오, 캡션 텍스트, 메타데이터)을 Google Drive에 업로드합니다.
    """
    try:
        service = get_drive_service()
        raw_root = os.getenv("GDRIVE_FOLDER_ID", "")
        root_folder_id = raw_root.split("?")[0].strip() if raw_root else ""

        if not root_folder_id:
            print("  ⚠️ [.env] GDRIVE_FOLDER_ID가 지정되지 않았습니다.")
            root_folder_id = find_or_create_folder(service, "인스타그램_릴스_자동화")

        today_str = datetime.date.today().strftime("%Y-%m-%d")
        subfolder_name = custom_folder_name or f"Reel_{today_str}_{int(datetime.datetime.now().timestamp())}"
        target_folder_id = find_or_create_folder(service, subfolder_name, parent_id=root_folder_id)

        print(f"[GDRIVE] Google Drive 업로드 시작 (대상 폴더: '{subfolder_name}')")

        results = {}

        # 1. 비디오 업로드 (공개 권한 설정 -> 직다운로드 URL 생성)
        video_res = upload_file_to_drive(video_path, folder_id=target_folder_id, make_public=True)
        results["video"] = video_res
        print(f"  ✅ 비디오 업로드 완료 -> {video_res['name']} ({video_res['link']})")
        if video_res.get("direct_url"):
            print(f"  🔗 직접 다운로드 URL: {video_res['direct_url']}")

        # 2. 캡션 업로드
        if caption_path and Path(caption_path).is_file():
            cap_res = upload_file_to_drive(caption_path, folder_id=target_folder_id)
            results["caption"] = cap_res
            print(f"  ✅ 캡션 텍스트 업로드 완료 -> {cap_res['name']}")

        # 3. 메타데이터 업로드
        if metadata_path and Path(metadata_path).is_file():
            meta_res = upload_file_to_drive(metadata_path, folder_id=target_folder_id)
            results["metadata"] = meta_res
            print(f"  ✅ 메타데이터 업로드 완료 -> {meta_res['name']}")

        results["folder_id"] = target_folder_id
        results["folder_link"] = f"https://drive.google.com/drive/folders/{target_folder_id}"
        print(f"[GDRIVE] 📁 Drive 폴더 공유 링크: {results['folder_link']}")
        return results

    except Exception as e:
        err_msg = str(e)
        if "storageQuotaExceeded" in err_msg:
            print("\n  💡 [안내] Google Drive 저장 용량 제한 에러 발생")
            print("     이유: 서비스 계정으로 업로드를 시도했습니다. 서비스 계정은 자체 용량이 0 Byte입니다.")
            print("     해결책: 'python pipeline/gdrive_oauth_setup.py' 를 실행해 사용자 OAuth로 재인증하세요.\n")
        elif "OAuth" in err_msg or "token.json" in err_msg:
            print(f"\n  💡 [안내] {err_msg}\n")
        else:
            print(f"[ERROR] Google Drive 업로드 중 오류 발생: {e}")
        return {"error": err_msg}