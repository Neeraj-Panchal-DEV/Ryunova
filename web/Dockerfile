# RyuNova Django — production image (EC2 / ECR)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8011

ENV USE_WHITENOISE=true
ENV DEBUG=false

CMD ["sh", "-c", "python manage.py collectstatic --noinput && exec gunicorn ryunova_web.wsgi:application --bind 0.0.0.0:8011 --timeout 120 --workers 3"]
