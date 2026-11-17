FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin django
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt "gunicorn>=22,<24"
COPY . /app
RUN chmod +x /app/hostinger/entrypoint.sh && chown -R django:django /app
USER django
EXPOSE 8000
CMD ["/app/hostinger/entrypoint.sh"]
