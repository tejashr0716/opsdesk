FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 appuser
COPY app ./app
COPY database ./database
COPY scripts ./scripts
COPY static ./static
COPY start.sh .
RUN chmod +x start.sh && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["./start.sh"]
