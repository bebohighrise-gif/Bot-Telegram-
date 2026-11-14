FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --create-home --uid 10001 bot \
    && mkdir /data && chown bot /data
COPY bot.py main.py web_server.py ./
COPY webapp ./webapp
EXPOSE 8080
USER bot
VOLUME ["/data"]
CMD ["python", "main.py"]
