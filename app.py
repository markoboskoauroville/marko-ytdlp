import streamlit as st
import yt_dlp
import os
import tempfile
import json
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Internet → Google Drive",
    page_icon="🌐",
    layout="centered"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { max-width: 720px; margin: 0 auto; }
    .stTextInput input { font-size: 15px; }
    .status-box {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 16px;
        font-family: monospace;
        font-size: 13px;
        color: #cdd6f4;
        margin-top: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ── Google Drive setup ────────────────────────────────────────────────────────
@st.cache_resource
def get_drive_service():
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"])
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        st.error(f"Google Drive connection failed: {e}")
        return None

def get_or_create_folder(service, folder_name, parent_id=None):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]

def upload_to_drive(service, file_path, folder_id):
    file_name = Path(file_path).name
    mime_type = "application/octet-stream"
    ext = Path(file_path).suffix.lower()
    mime_map = {
        ".mp4": "video/mp4", ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4", ".webm": "video/webm",
        ".mkv": "video/x-matroska", ".jpg": "image/jpeg",
        ".png": "image/png", ".pdf": "application/pdf",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")
    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
    file_meta = {"name": file_name, "parents": [folder_id]}
    uploaded = service.files().create(
        body=file_meta, media_body=media, fields="id, name, webViewLink"
    ).execute()
    return uploaded

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🌐 Internet → Google Drive")
st.caption("Paste any link. Download via yt-dlp. Land directly in your Drive.")

st.divider()

url = st.text_input("🔗 URL", placeholder="https://www.instagram.com/... or YouTube, Twitter, TikTok...")

col1, col2 = st.columns(2)
with col1:
    format_choice = st.selectbox("Format", [
        "Best video+audio (mp4)",
        "Audio only (mp3)",
        "Audio only (m4a)",
        "Best video (no merge)",
        "Worst (smallest file)",
    ])
with col2:
    folder_name = st.text_input("Drive folder name", value="yt-dlp-downloads")

cookies_option = st.radio("Cookies", ["None needed", "Paste cookies", "Upload cookies.txt"], horizontal=True)

cookies_text = None
cookies_file_path = None

if cookies_option == "Paste cookies":
    cookies_text = st.text_area(
        "Paste cookies (Netscape format or key=value pairs)",
        height=120,
        placeholder="datr=xxx; sessionid=xxx; csrftoken=xxx ..."
    )

elif cookies_option == "Upload cookies.txt":
    uploaded_file = st.file_uploader("Upload cookies.txt", type=["txt"])
    if uploaded_file:
        cookies_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="wb")
        cookies_file_path.write(uploaded_file.read())
        cookies_file_path.flush()
        cookies_file_path = cookies_file_path.name
        st.success("cookies.txt loaded")

st.divider()

if st.button("🚀 Download & Upload to Drive", type="primary", use_container_width=True):
    if not url:
        st.warning("Please enter a URL.")
    else:
        service = get_drive_service()
        if not service:
            st.stop()

        log_area = st.empty()
        log_lines = []

        def log(msg):
            log_lines.append(msg)
            log_area.markdown(
                "<div class='status-box'>" + "<br>".join(log_lines) + "</div>",
                unsafe_allow_html=True
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Build yt-dlp options
            fmt_map = {
                "Best video+audio (mp4)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "Audio only (mp3)": "bestaudio/best",
                "Audio only (m4a)": "bestaudio[ext=m4a]/bestaudio/best",
                "Best video (no merge)": "best",
                "Worst (smallest file)": "worst",
            }

            ydl_opts = {
                "format": fmt_map[format_choice],
                "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
            }

            if format_choice == "Audio only (mp3)":
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]

            # Handle cookies
            if cookies_option == "Paste cookies" and cookies_text:
                cookie_file = os.path.join(tmpdir, "cookies.txt")
                lines = ["# Netscape HTTP Cookie File"]
                for pair in cookies_text.replace(";", "\n").splitlines():
                    pair = pair.strip()
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        lines.append(f".instagram.com\tTRUE\t/\tTRUE\t0\t{k.strip()}\t{v.strip()}")
                with open(cookie_file, "w") as f:
                    f.write("\n".join(lines))
                ydl_opts["cookiefile"] = cookie_file

            elif cookies_option == "Upload cookies.txt" and cookies_file_path:
                ydl_opts["cookiefile"] = cookies_file_path

            # Download
            log("⬇️ Starting download...")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get("title", "file")
                log(f"✅ Downloaded: {title}")
            except Exception as e:
                log(f"❌ Download failed: {e}")
                st.stop()

            # Find downloaded files
            files = list(Path(tmpdir).glob("*"))
            files = [f for f in files if f.is_file() and "cookies" not in f.name]

            if not files:
                log("❌ No files found after download.")
                st.stop()

            log(f"📁 {len(files)} file(s) ready for upload")

            # Get or create Drive folder
            try:
                target_folder_id = st.secrets.get("GDRIVE_FOLDER_ID", None)
                if target_folder_id:
                    folder_id = get_or_create_folder(service, folder_name, parent_id=target_folder_id)
                else:
                    folder_id = get_or_create_folder(service, folder_name)
                log(f"📂 Drive folder ready: {folder_name}")
            except Exception as e:
                log(f"❌ Folder creation failed: {e}")
                st.stop()

            # Upload each file
            for fp in files:
                log(f"⬆️ Uploading {fp.name} ({round(fp.stat().st_size / 1024 / 1024, 1)} MB)...")
                try:
                    result = upload_to_drive(service, str(fp), folder_id)
                    log(f"✅ Uploaded: [{result['name']}]({result['webViewLink']})")
                    st.success(f"[Open in Google Drive]({result['webViewLink']})")
                except Exception as e:
                    log(f"❌ Upload failed: {e}")

            log("🎉 All done!")

st.divider()
st.caption("Supports: YouTube, Instagram, TikTok, Twitter/X, Facebook, Vimeo, SoundCloud and 1000+ more sites via yt-dlp")
