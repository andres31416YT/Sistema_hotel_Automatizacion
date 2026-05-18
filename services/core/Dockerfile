FROM python:3.10-slim

WORKDIR /core

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY now.py .
COPY core_auth_settings.py .
COPY prompts/ prompts/
COPY admin_service/ admin_service/
COPY customer_service/ customer_service/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/core

EXPOSE 8080

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
