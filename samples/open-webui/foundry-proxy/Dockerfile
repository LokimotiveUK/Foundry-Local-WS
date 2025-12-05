# Foundry Proxy - Auto-discovers Foundry Local's dynamic port
FROM python:3.11-slim

WORKDIR /app

# No dependencies needed - uses standard library only
COPY proxy.py .

EXPOSE 8080

CMD ["python", "-u", "proxy.py"]
