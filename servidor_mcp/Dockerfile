# Imagem do servidor MCP do Observatório de Taxas.
# Construa a partir da RAIZ do repositório (o servidor reusa scripts/ e config.yml):
#   docker build -f servidor_mcp/Dockerfile -t observatorio-mcp .
#   docker run --rm -p 8000:8000 observatorio-mcp
# Funciona igual no Render (runtime docker) e no Hugging Face Spaces (SDK docker).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app

COPY servidor_mcp/requirements.txt servidor_mcp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r servidor_mcp/requirements.txt

# Só o necessário: o servidor, os geradores que contêm as fórmulas e o config.
COPY config.yml ./
COPY scripts/build_pages.py scripts/build_correcao.py scripts/fontes.py scripts/
COPY servidor_mcp/ servidor_mcp/

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'),timeout=4)"
CMD ["sh", "-c", "uvicorn servidor_mcp.servidor:app --host 0.0.0.0 --port ${PORT} --no-server-header --no-access-log"]
