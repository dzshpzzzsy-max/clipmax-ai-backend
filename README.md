# CLIPMAX AI Backend — MVP starter

This service receives a video at `POST /v1/analyze`, cuts a requested number of vertical MP4 sample clips with FFmpeg, and returns URLs for playback/download.

## Important MVP limitation

This first backend starter proves the upload → processing → clip delivery pipeline. It does **not yet use AI to identify viral moments**, transcribe speech, or generate captions. The current clips are sampled across the source video. AI highlight ranking/transcription is a separate next development step.

## Deploy on Render

1. Push these files to a GitHub repository named `clipmax-ai-backend`.
2. In Render, create **New Web Service** and connect that repository.
3. Choose Docker runtime (Render detects the Dockerfile).
4. Deploy. The service exposes `/health` and `/v1/analyze`.

## Connect the website

After Render gives you a public HTTPS URL, update `API_BASE` in the website repository's `app.js` to that URL, for example `https://your-service.onrender.com`, then commit the change in GitHub. Do not include a trailing slash.

## Notes

- This starter uses local temporary storage for uploaded source videos and local output storage for clips. Render instance restarts or redeployments can remove generated clips. Production needs persistent/object storage, job queues, authentication, upload limits, and monitoring.
- Large videos may exceed hosting limits or time out. Start with short test videos.
- Set `ALLOWED_ORIGINS` to your exact website origin if the domain changes.
