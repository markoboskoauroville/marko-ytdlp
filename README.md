# 🌐 Internet → Google Drive Downloader

Paste any URL. Download via yt-dlp. Land directly in your Google Drive.

Supports YouTube, Instagram, TikTok, Twitter/X, Facebook, Vimeo, SoundCloud and 1000+ more.

---

## 🚀 Deploy on Streamlit Cloud (Step by Step)

### 1. Fork or push this repo to GitHub

Push all files to a new GitHub repo. Do NOT include `.streamlit/secrets.toml`.

### 2. Set up Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable **Google Drive API** under APIs & Services
4. Go to **APIs & Services → Credentials → Create Credentials → Service Account**
5. Name it anything, click Done
6. Click the service account → **Keys** tab → **Add Key → JSON**
7. Download the JSON file — you'll paste its contents into Streamlit secrets

### 3. Share your Google Drive folder with the service account

1. Open Google Drive, create a folder called `yt-dlp-downloads` (or any name)
2. Right-click the folder → Share
3. Paste the service account email (looks like `name@project.iam.gserviceaccount.com`)
4. Give it **Editor** access
5. Copy the folder ID from the URL: `drive.google.com/drive/folders/COPY_THIS_PART`

### 4. Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect your GitHub account
3. Select the repo, branch `main`, file `app.py`
4. Click **Advanced settings → Secrets** and paste:

```toml
GOOGLE_SERVICE_ACCOUNT_JSON = '''
{ ...paste your entire service account JSON here... }
'''

GDRIVE_FOLDER_ID = "your-folder-id-here"
```

5. Deploy!

---

## 🍪 Cookies for private/restricted content

For Instagram stories, private accounts, age-restricted YouTube etc., you need cookies.

**Option A — Paste:** Copy from your browser (use EditThisCookie extension), paste as `key=value; key2=value2`

**Option B — Upload:** Export cookies.txt from your browser via the "Get cookies.txt LOCALLY" extension and upload it in the app.

---

## ⚙️ Format options

| Option | Result |
|--------|--------|
| Best video+audio (mp4) | Merges best streams, saves as .mp4 |
| Audio only (mp3) | Extracts and converts audio |
| Audio only (m4a) | Extracts audio without conversion |
| Best video (no merge) | Single stream, no ffmpeg needed |
| Worst (smallest file) | Lowest quality, fastest download |

---

## 📝 Notes

- Streamlit Cloud free tier has a memory limit (~1GB), so very large files may fail. For files over 500MB consider a paid tier or self-hosting.
- yt-dlp updates frequently. If a site stops working, bump the yt-dlp version in `requirements.txt`.
- ffmpeg is available on Streamlit Cloud by default, needed for mp4 merging and mp3 conversion.
