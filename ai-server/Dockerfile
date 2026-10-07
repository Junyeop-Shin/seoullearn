FROM python:3.12-slim

WORKDIR /project/ai-server
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROJECT_ROOT=/project \
    HF_HOME=/hf-cache

COPY requirements.txt .
# CPU 전용 torch를 먼저 깔아 이미지 크기를 줄인다
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
