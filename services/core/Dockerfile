FROM python:3.10-slim

WORKDIR /core

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lib/ lib/
COPY agents/ agents/
COPY main.py .
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/core:/

EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]