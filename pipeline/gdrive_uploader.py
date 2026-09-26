"""
Google Drive Automatic Uploader Module for Instagram Reels Pipeline.
Uses Service Account credentials to upload videos, captions, and metadata.
Creates date-based subfolders and sets public read permissions for direct download.
"""
import os
import sys
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


def get_drive_service():
    """Google Drive API 서비스 객체를 서비스 계정 증명으로 생성합니다."""
    import google.auth
    from googleapiclient.discovery import build

    sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not sa_path or not os.path.isfile(sa_path):
        raise FileNotFoundError(f"서비스 계정 키 파일을 찾을 수 없습니다: {sa_path}")

    scopes = ["https://www.googleapis.com/auth/drive"]
    credentials = google.auth.load_credentials_from_file(sa_path, scopes=scopes)[0]
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
            print("     이유: 구글 서비스 계정(Bot)은 자체 용량이 0 Byte입니다.")
            print("     해결책: 내 구글 드라이브에 폴더 생성 -> '공유' 클릭")
            print("     -> 서비스 계정 이메일에 '편집자' 권한 부여")
            print("     -> 폴더 URL 주소의 폴더 ID를 .env 파일의 GDRIVE_FOLDER_ID= 에 입력하면 완료!\n")
        else:
            print(f"[ERROR] Google Drive 업로드 중 오류 발생: {e}")
        return {"error": err_msg}