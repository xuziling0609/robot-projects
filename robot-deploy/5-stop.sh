#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ 未安装 Docker Compose"
    exit 1
fi

# 加载环境变量
source .env
export DB_TYPE="${DB_TYPE:-opengauss}"
export COMPOSE_PROFILES="${DB_TYPE}"

# 解析目标服务（支持命令行传参，如 ./5-stop.sh java 或 ./5-stop.sh 1）
TARGET="${1:-}"

if [ -z "$TARGET" ]; then
    echo "===================================================="
    echo "请选择要停止的服务容器 (当前数据库模式: ${DB_TYPE}):"
    echo "  0) 全部服务容器 (All Services) - [默认]"
    echo "  1) Java 业务后端   (app-java)"
    echo "  2) Nginx 网关      (app-nginx)"
    echo "  3) 数据库          (${DB_TYPE})"
    echo "  4) Redis 缓存      (app-redis)"
    echo "  5) EMQX 消息队列   (app-emqx)"
    echo "  6) SeaweedFS 存储  (app-seaweedfs)"
    echo "  7) go2rtc 视频流   (app-go2rtc)"
    echo "===================================================="
    read -r -p "请输入选项序号 [0-7] 或服务名 (默认: 0): " input_val
    TARGET="${input_val:-0}"
fi

case "$TARGET" in
    0|all|ALL|"")
        echo "正在停止并清理所有服务容器..."
        $COMPOSE_CMD --profile "$DB_TYPE" down
        echo "✅ 全部服务已停止"
        ;;
    1|java|app-java)
        echo "正在停止 Java 业务后端 (app-java)..."
        $COMPOSE_CMD --profile "$DB_TYPE" stop app-java
        echo "✅ app-java 已停止"
        ;;
    2|nginx|app-nginx)
        echo "正在停止 Nginx 网关 (app-nginx)..."
        $COMPOSE_CMD --profile "$DB_TYPE" stop nginx
        echo "✅ app-nginx 已停止"
        ;;
    3|db|database|opengauss|mysql)
        echo "正在停止数据库容器 (${DB_TYPE})..."
        $COMPOSE_CMD --profile "$DB_TYPE" stop "$DB_TYPE"
        echo "✅ 数据库 (${DB_TYPE}) 已停止"
        ;;
    4|redis|app-redis)
        echo "正在停止 Redis 缓存 (app-redis)..."
        $COMPOSE_CMD --profile "$DB_TYPE" stop redis
        echo "✅ app-redis 已停止"
        ;;
    5|emqx|app-emqx)
        echo "正在停止 EMQX 消息队列 (app-emqx)..."
        $COMPOSE_CMD --profile "$DB_TYPE" stop emqx
        echo "✅ app-emqx 已停止"
        ;;
    6|seaweedfs|app-seaweedfs)
        echo "正在停止 SeaweedFS 存储 (app-seaweedfs)..."
        $COMPOSE_CMD --profile "$DB_TYPE" stop seaweedfs
        echo "✅ app-seaweedfs 已停止"
        ;;
    7|go2rtc|app-go2rtc)
        echo "正在停止 go2rtc 视频流 (app-go2rtc)..."
        $COMPOSE_CMD --profile "$DB_TYPE" stop go2rtc
        echo "✅ app-go2rtc 已停止"
        ;;
    *)
        echo "正在停止指定服务: ${TARGET} ..."
        $COMPOSE_CMD --profile "$DB_TYPE" stop "${TARGET}"
        echo "✅ ${TARGET} 已停止"
        ;;
esac