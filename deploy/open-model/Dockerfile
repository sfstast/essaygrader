FROM python:3.12-slim
RUN useradd -m -u 1000 worker
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=worker:worker . .
USER worker
ENV HF_HOME=/home/worker/.cache/huggingface
EXPOSE 7860
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860", "--no-access-log"]
