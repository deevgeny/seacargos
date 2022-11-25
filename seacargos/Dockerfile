FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt --no-cache-dir --upgrade pip --root-user-action=ignore

COPY . .

CMD ["gunicorn", "wsgi:app", "--bind", "0:5000"]
