import streamlit as st
import yt_dlp
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Internet Downloader",
    page_icon="🌐",
    layout="centered"
)

st.markdown("""
<style>
    .status-box {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 16px;
        font-family: monospace;
        font-size: 13px;
        color: #cdd6f4;
        margin-top: 12px;
        line-height: 1.8;
    }
    .status-box a { color: #89dceb; }
</style>
""", unsafe_allow_html=True)

# ── Google Drive helpers ──────────────────────────────────────────────────────
@st.cache_resource
def get_drive_service():
    try:
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        st.error(f"Google Drive connection failed: {e}")
        return None

def get_or_create_folder(service, folder_name):
    query = (
        f"name='{folder_name}' "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder"
    }
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]

def upload_to_drive(service, file_path, folder_id):
    file_name = Path(file_path).name
    ext = Path(file_path).suffix.lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".pdf": "application/pdf",
        ".zip": "application/zip",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")
    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
    file_meta = {"name": file_name, "parents": [folder_id]}
    uploaded = service.files().create(
        body=file_meta,
        media_body=media,
        fields="id, name, webViewLink"
    ).execute()
    return uploaded

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🌐 Internet Downloader")
st.caption("Paste any link, choose your destination, download via yt-dlp.")
st.divider()

# ── URL ───────────────────────────────────────────────────────────────────────
url = st.text_input(
    "🔗 URL",
    placeholder="YouTube, Instagram, TikTok, Twitter/X, Vimeo, SoundCloud..."
)

# ── Destination radio ─────────────────────────────────────────────────────────
destination = st.radio(
    "📦 Save to",
    ["☁️ Google Drive", "💾 Download to my device"],
    horizontal=True
)

# ── Options row ───────────────────────────────────────────────────────────────
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
    if "Drive" in destination:
        folder_name = st.text_input(
            "Drive folder",
            value=st.secrets.get("GDRIVE_FOLDER_NAME", "_yt-dlp-downloads")
        )
    else:
        st.write("")
        st.caption("File will be served as a browser download.")
        folder_name = None

# ── Cookies ───────────────────────────────────────────────────────────────────
cookies_option = st.radio(
    "🍪 Cookies",
    ["None needed", "Paste cookies", "Upload cookies.txt"],
    horizontal=True
)

cookies_text = None
cookies_file_path = None

if cookies_option == "Paste cookies":
    cookies_text = st.text_area(
        "Paste as: key=value; key2=value2",
        height=90,
        placeholder="datr=xxx; sessionid=xxx; csrftoken=xxx"
    )
elif cookies_option == "Upload cookies.txt":
    uploaded_cookie = st.file_uploader("Upload cookies.txt", type=["txt"])
    if uploaded_cookie:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="wb")
        tmp.write(uploaded_cookie.read())
        tmp.flush()
        cookies_file_path = tmp.name
        st.success("cookies.txt loaded")

st.divider()

# ── Download button ───────────────────────────────────────────────────────────
if st.button("🚀 Download", type="primary", use_container_width=True):

    if not url:
        st.warning("Please enter a URL.")
        st.stop()

    log_area = st.empty()
    log_lines = []

    def log(msg):
        log_lines.append(msg)
        log_area.markdown(
            "<div class='status-box'>" + "<br>".join(log_lines) + "</div>",
            unsafe_allow_html=True
        )

    # Use a persistent temp dir so local download button can still read the file
    tmpdir = tempfile.mkdtemp()

    try:
        fmt_map = {
            "Best video+audio (mp4)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "Audio only (mp3)":       "bestaudio/best",
            "Audio only (m4a)":       "bestaudio[ext=m4a]/bestaudio/best",
            "Best video (no merge)":  "best",
            "Worst (smallest file)":  "worst",
        }

        ydl_opts = {
            "format":      fmt_map[format_choice],
            "outtmpl":     os.path.join(tmpdir, "%(title)s.%(ext)s"),
            "quiet":       True,
            "no_warnings": True,
        }

        if format_choice == "Audio only (mp3)":
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]

        # Cookies
        if cookies_option == "Paste cookies" and cookies_text:
            cookie_file = os.path.join(tmpdir, "cookies.txt")
            lines = ["# Netscape HTTP Cookie File"]
            for pair in cookies_text.replace(";", "\n").splitlines():
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    lines.append(
                        f".instagram.com\tTRUE\t/\tTRUE\t0\t{k.strip()}\t{v.strip()}"
                    )
            with open(cookie_file, "w") as f:
                f.write("\n".join(lines))
            ydl_opts["cookiefile"] = cookie_file
        elif cookies_option == "Upload cookies.txt" and cookies_file_path:
            ydl_opts["cookiefile"] = cookies_file_path

        # Download
        log("⬇️ Fetching media info and downloading...")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "file")
            log(f"✅ Downloaded: {title}")
        except Exception as e:
            log(f"❌ Download failed: {e}")
            st.stop()

        files = [
            f for f in Path(tmpdir).glob("*")
            if f.is_file() and "cookies" not in f.name
        ]
        if not files:
            log("❌ No output files found.")
            st.stop()

        size_mb = sum(f.stat().st_size for f in files) / 1024 / 1024
        log(f"📦 {len(files)} file(s) — {round(size_mb, 1)} MB total")

        # ── Google Drive path ─────────────────────────────────────────────────
        if "Drive" in destination:
            service = get_drive_service()
            if not service:
                st.stop()
            try:
                folder_id = get_or_create_folder(service, folder_name)
                log(f"📂 Drive folder ready: {folder_name}")
            except Exception as e:
                log(f"❌ Folder error: {e}")
                st.stop()

            for fp in files:
                log(f"⬆️ Uploading {fp.name}...")
                try:
                    result = upload_to_drive(service, str(fp), folder_id)
                    log(
                        f"✅ Saved → "
                        f"<a href='{result['webViewLink']}' target='_blank'>"
                        f"{result['name']}</a>"
                    )
                    st.success(f"[Open in Google Drive ↗]({result['webViewLink']})")
                except Exception as e:
                    log(f"❌ Upload failed: {e}")

        # ── Local download path ───────────────────────────────────────────────
        else:
            if len(files) == 1:
                fp = files[0]
                data = fp.read_bytes()
                st.download_button(
                    label=f"⬇️ Save {fp.name}",
                    data=data,
                    file_name=fp.name,
                    mime="application/octet-stream",
                    use_container_width=True,
                )
                log(f"✅ Ready — click the button above to save {fp.name}")
            else:
                zip_path = os.path.join(tmpdir, "download.zip")
                with zipfile.ZipFile(zip_path, "w") as zf:
                    for fp in files:
                        zf.write(fp, fp.name)
                data = Path(zip_path).read_bytes()
                st.download_button(
                    label=f"⬇️ Save all as ZIP ({len(files)} files)",
                    data=data,
                    file_name="download.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
                log(f"✅ {len(files)} files zipped — click the button above to save")

        log("🎉 All done!")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

st.divider()
st.caption(
    "Supports YouTube, Instagram, TikTok, Twitter/X, Facebook, "
    "Vimeo, SoundCloud and 1000+ more via yt-dlp"
)
