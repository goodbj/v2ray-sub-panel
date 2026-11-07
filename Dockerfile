FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 数据目录挂载点
VOLUME ["/data"]

ENV DATA_DIR=/data
ENV PORT=8000
ENV AUTO_FETCH=1
ENV REFRESH_INTERVAL=1800

EXPOSE 8000

CMD ["python", "app.py"]
