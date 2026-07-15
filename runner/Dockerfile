FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /runner
RUN addgroup --system runner && adduser --system --ingroup runner runner
COPY runner.py ./runner.py
USER runner
CMD ["python", "runner.py"]
