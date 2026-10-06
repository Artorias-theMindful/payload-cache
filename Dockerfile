FROM python:3.14-slim

WORKDIR /app

# Dependencies first, so code changes do not invalidate the install layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --no-create-home app
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
