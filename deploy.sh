#!/usr/bin/env bash
# Redeploy Campus Copilot (agent API + web app) to Cloud Run.
# Live URL stays the same: https://campus-copilot-261781875474.us-central1.run.app
# Needs: gcloud installed and logged in (gcloud auth login) with access to the project.
# Takes ~5 minutes. Public access and settings carry over between deploys.
set -euo pipefail
cd "$(dirname "$0")"

GCLOUD="${GCLOUD:-$(command -v gcloud || echo "$HOME/google-cloud-sdk/bin/gcloud")}"
PROJECT=campus-copilot-514718
REGION=us-central1

"$GCLOUD" run deploy campus-copilot \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=gemini-3.5-flash,GEMINI_LIVE_MODEL=gemini-live-2.5-flash-native-audio,GEMINI_LIVE_LOCATION=us-central1" \
  --memory 1Gi --cpu 1 --min-instances 1 --max-instances 1 \
  --timeout 900 --session-affinity --quiet

echo "Live: https://campus-copilot-261781875474.us-central1.run.app"
