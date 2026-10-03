FROM python:3.12-slim

WORKDIR /app

COPY extracted_bot/RUDRILA_Bitget_AI_v1_batch_01_40 /app/RUDRILA_Bitget_AI_v1_batch_01_40

WORKDIR /app/RUDRILA_Bitget_AI_v1_batch_01_40

RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/RUDRILA_Bitget_AI_v1_batch_01_40/src
ENV RUDRILA_MODE=demo
ENV LIVE_TRADING=false
ENV PYTHONUNBUFFERED=1

CMD ["python","-m","rudrila.main","--demo-run","315360000"]
