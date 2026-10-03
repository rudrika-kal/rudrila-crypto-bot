FROM python:3.12-slim

WORKDIR /app

COPY RUDRILA_Bitget_AI_v1_1_DEMO_READY.zip /tmp/bot.zip

RUN python - <<'PY'
import zipfile
zipfile.ZipFile('/tmp/bot.zip').extractall('/app')
PY

WORKDIR /app/RUDRILA_Bitget_AI_v1_batch_01_40

# HTTP400 repair overlay: preserve the packaged bot while replacing only the
# REST client with the audited source that surfaces Bitget code/msg.
COPY extracted_bot/RUDRILA_Bitget_AI_v1_batch_01_40/src/rudrila/rest_client.py /app/RUDRILA_Bitget_AI_v1_batch_01_40/src/rudrila/rest_client.py

RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/RUDRILA_Bitget_AI_v1_batch_01_40/src
ENV RUDRILA_MODE=demo
ENV LIVE_TRADING=false
ENV PYTHONUNBUFFERED=1

CMD ["python","-m","rudrila.main","--demo-run","315360000"]
