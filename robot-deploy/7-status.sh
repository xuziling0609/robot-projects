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

if [ -f .env ]; then
    # 加载环境变量
    source .env
fi
export DB_TYPE="${DB_TYPE:-opengauss}"
export COMPOSE_PROFILES="${DB_TYPE}"

echo "===================================================="
echo "当前容器状态 (Profile: ${DB_TYPE}):"
echo "===================================================="
{
    echo -e "NAME\tIMAGE\tSTATUS\tHEALTHY"
    $COMPOSE_CMD --profile "$DB_TYPE" ps -a --format "{{.Name}}\t{{.Image}}\t{{.Status}}" | awk -F'\t' '
    {
        name=$1
        image=$2
        status_field=$3
        health="-"
        
        if (match(status_field, /\((healthy|unhealthy|starting)\)/)) {
            health = substr(status_field, RSTART+1, RLENGTH-2)
            status_field = substr(status_field, 1, RSTART-1)
            # trim trailing space
            sub(/ *$/, "", status_field)
        }
        
        print name "\t" image "\t" status_field "\t" health
    }
    '
} | column -t -s $'\t' | awk '
BEGIN {
    GREEN="\033[32m"; RED="\033[31m"; YELLOW="\033[33m"; RESET="\033[0m"
}
NR==1 {
    print "\033[1m" $0 RESET
    next
}
{
    color=RESET
    if ($0 ~ /Up/) {
        if ($0 ~ /healthy$/) color=GREEN
        else color=YELLOW
    } else if ($0 ~ /Exited/) {
        color=RED
    }
    print color $0 RESET
}'
