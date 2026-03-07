# ============================================================
# AutoDev Pipeline — 多阶段 Docker 构建
# 对齐: OPS-001 §2, ARCH-002
# ============================================================

# ── Stage 1: Builder ─────────────────────────────
FROM python:3.10-slim AS builder

WORKDIR /build

COPY pyproject.toml .
COPY orchestrator/ orchestrator/
COPY README.md .

RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: Runtime ─────────────────────────────
FROM python:3.10-slim AS runtime

LABEL maintainer="lucas-realman"
LABEL description="AutoDev Pipeline — AI 自动化开发流水线平台"
LABEL version="3.0.0"

# 安全: 非 root 运行
RUN groupadd -r autodev && useradd -r -g autodev -m autodev

WORKDIR /app

# 从 builder 复制安装产物
COPY --from=builder /install /usr/local
COPY orchestrator/ orchestrator/
COPY pyproject.toml .
COPY README.md .

# 创建必要目录
RUN mkdir -p /app/reports /app/logs && \
    chown -R autodev:autodev /app

# 配置文件挂载点
VOLUME ["/app/configs", "/app/reports", "/app/logs"]

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_FORMAT=json \
    LOG_LEVEL=INFO

# 切换到非 root 用户
USER autodev

# 健康检查: 通过 Dashboard API
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8080/api/status'); assert r.status_code == 200" || exit 1

# 独立 Dashboard API 端口
EXPOSE 8080

# 默认入口: 启动独立 Dashboard API（不直接运行 Orchestrator 主流程）
CMD ["python", "-m", "uvicorn", "orchestrator.dashboard:app", "--host", "0.0.0.0", "--port", "8080"]
