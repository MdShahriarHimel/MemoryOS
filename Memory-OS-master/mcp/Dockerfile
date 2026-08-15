FROM python:3.12-slim
WORKDIR /app
COPY mcp/requirements.txt ./mcp/requirements.txt
COPY mcp/ ./mcp/
COPY scripts/mcp_stdio_server.py ./scripts/
RUN pip install --no-cache-dir -r mcp/requirements.txt httpx
ENV PYTHONPATH=/app
ENV MEMORY_OS_API_URL=http://api:8000
CMD ["python", "scripts/mcp_stdio_server.py"]
