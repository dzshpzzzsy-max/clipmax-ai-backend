import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).parent
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/tmp/clipmax-output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))

app = FastAPI(title="CLIPMAX AI Backend", version="0.1.0")

allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://clipmax-ai.pages.dev,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/clips", StaticFiles(directory=str(OUTPUT_DIR)), name="clips")


@app.get("/")
def root():
    return {"app": "CLIPMAX AI", "status": "online", "message": "Backend is running."}


@app.get("/health")
def health():
    return {"status": "ok"}


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3000:] or "Video processing failed")
    return result.stdout


def probe_duration(path: Path) -> float:
    output = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ])
    return float(output.strip())


def make_clips(video_path: Path, clip_count: int):
    duration = probe_duration(video_path)
    if duration < 8:
        raise ValueError("Please upload a video that is at least 8 seconds long.")

    # Initial MVP: evenly spaced sample moments. This verifies the full
    # upload/transcode/download pipeline. AI highlight ranking is a later step.
    count = max(1, min(10, clip_count))
    clip_length = min(45.0, max(8.0, duration / max(count, 1)))
    max_start = max(0.0, duration - clip_length)
    clips = []

    for index in range(count):
        start = max_start * (index / max(count - 1, 1)) if count > 1 else max_start / 2
        filename = f"{uuid.uuid4().hex[:12]}-clip-{index + 1}.mp4"
        output_path = OUTPUT_DIR / filename

        run([
            "ffmpeg", "-y", "-ss", str(start), "-i", str(video_path),
            "-t", str(clip_length),
            "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(output_path)
        ])

        clips.append({
            "title": f"CLIPMAX Clip {index + 1}",
            "url": f"/clips/{filename}",
            "startSeconds": round(start, 2),
            "endSeconds": round(start + clip_length, 2),
            "durationSeconds": round(clip_length, 2),
            "score": 0,
            "transcript": "MVP sample clip. AI highlight detection and captions are not enabled yet."
        })
    return clips


@app.post("/v1/analyze")
async def analyze(
    video: UploadFile = File(...),
    clip_count: int = Form(5)
):
    if not video.filename:
        raise HTTPException(status_code=400, detail="Please choose a video.")
    if video.content_type and not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Please upload a video file.")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise HTTPException(status_code=500, detail="Video tools are not installed on the server.")

    temp_path = None
    try:
        suffix = Path(video.filename).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp_path = Path(temp.name)
            size = 0
            while chunk := await video.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(status_code=413, detail=f"Video is larger than {MAX_UPLOAD_MB} MB.")
                temp.write(chunk)

        clips = make_clips(temp_path, clip_count)
        return {"clips": clips}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(exc)[:1000]}")
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        await video.close()
