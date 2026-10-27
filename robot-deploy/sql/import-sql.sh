#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

# 1. 加载环境变量
if [ -f ../.env ]; then
    source ../.env
elif [ -f .env ]; then
    source .env
fi

CHOSEN_DB=""
# 检查是否通过参数传入：如 ./import-sql.sh mysql 或 ./import-sql.sh opengauss
if [ -n "${1:-}" ]; then
    case "$1" in
        1|opengauss|openGauss)
            CHOSEN_DB="opengauss"
            shift # 移除第一个参数，方便后续处理额外的 SQL 文件路径参数
            ;;
        2|mysql|MySQL)
            CHOSEN_DB="mysql"
            shift
            ;;
        *)
            # 可能是传入了 SQL 文件路径，先不处理，等下面交互选择
            ;;
    esac
fi

if [ -z "${CHOSEN_DB}" ]; then
    CURRENT_CONFIGURED="${DB_TYPE:-opengauss}"
    echo "===================================================="
    echo "请选择要导入数据的数据库引擎 (Database Selection):"
    echo "  1) openGauss (国产高可用关系型数据库 6.0.0)"
    echo "  2) MySQL     (主流开源关系型数据库 8.0.46)"
    echo "===================================================="
    read -r -p "请输入选项序号 [1/2] (当前配置/默认: ${CURRENT_CONFIGURED}): " input_choice
    case "${input_choice}" in
        2|[mM][yY][sS][qQ][lL])
            CHOSEN_DB="mysql"
            ;;
        1|[oO][pP][eE][nN][gG][aA][uU][sS][sS])
            CHOSEN_DB="opengauss"
            ;;
        "")
            CHOSEN_DB="${CURRENT_CONFIGURED}"
            ;;
        *)
            echo "⚠️ 输入无效，采用默认配置: ${CURRENT_CONFIGURED}"
            CHOSEN_DB="${CURRENT_CONFIGURED}"
            ;;
    esac
fi

echo "✅ 已选择数据库: ${CHOSEN_DB}"

# 根据选择的数据库执行导入逻辑
if [ "${CHOSEN_DB}" = "mysql" ]; then
    CONTAINER_NAME="app-mysql"
    DB_NAME="${DB_NAME:-robot}"
    DB_USER="root"
    DB_PASS="${MYSQL_PASSWORD:-CHANGE_ME}"
    
    SQL_FILE=""
    CANDIDATE_PATHS=(
        "init-mysql.sql"
        "sql/init-mysql.sql"
        "${DATA_DIR:-/home/app}/init-mysql.sql"
        "${DATA_DIR:-/home/app}/sql/init-mysql.sql"
        "/home/deploy/init-mysql.sql"
        "../init-mysql.sql"
    )
    
    for p in "${CANDIDATE_PATHS[@]}"; do
        if [ -f "$p" ]; then
            SQL_FILE="$p"
            break
        fi
    done
    
    if [ -z "$SQL_FILE" ]; then
        if [ $# -ge 1 ] && [ -f "$1" ]; then
            SQL_FILE="$1"
        else
            echo "❌ 未找到 init-mysql.sql 文件！"
            echo "请将 init-mysql.sql 放在当前目录或通过参数指定：$0 mysql /path/to/init-mysql.sql"
            exit 1
        fi
    fi
    
    echo "=========================================="
    echo "准备导入 MySQL 数据库脚本: $SQL_FILE"
    echo "目标容器: $CONTAINER_NAME | 默认数据库: $DB_NAME"
    echo "=========================================="
    
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "❌ 容器 ${CONTAINER_NAME} 未运行，请先执行部署脚本"
        exit 1
    fi
    
    echo "正在检测 MySQL 服务连通性..."
    MAX_RETRIES=15
    RETRY_COUNT=0
    until docker exec "${CONTAINER_NAME}" mysqladmin ping -h localhost -u"${DB_USER}" -p"${DB_PASS}" --silent >/dev/null 2>&1; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "❌ MySQL 服务响应超时，请检查容器状态与密码是否正确！"
            exit 1
        fi
        echo "等待 MySQL 启动就绪 ($RETRY_COUNT/$MAX_RETRIES)..."
        sleep 2
    done
    echo "✅ MySQL 服务正常运行"
    
    echo "正在导入 SQL 脚本中，请稍候..."
    if docker exec -i "${CONTAINER_NAME}" mysql -u"${DB_USER}" -p"${DB_PASS}" --default-character-set=utf8mb4 < "$SQL_FILE"; then
        echo "✅ MySQL 数据库脚本导入完成！"
    else
        echo "❌ 导入执行失败，请检查上方错误提示！"
        exit 1
    fi
    echo "🎉 init-mysql.sql 数据库初始化成功！"

elif [ "${CHOSEN_DB}" = "opengauss" ]; then
    CONTAINER_NAME="app-opengauss"
    DB_NAME="postgres"
    DB_USER="gaussdb"
    DB_PASS="${OPENGAUSS_PASSWORD:-CHANGE_ME}"
    
    SQL_FILE=""
    CANDIDATE_PATHS=(
        "init-opengauss.sql"
        "sql/init-opengauss.sql"
        "${DATA_DIR:-/home/app}/init-opengauss.sql"
        "${DATA_DIR:-/home/app}/sql/init-opengauss.sql"
        "/home/deploy/init-opengauss.sql"
        "/home/app/init-scripts/opengauss/init.sql"
    )
    
    for p in "${CANDIDATE_PATHS[@]}"; do
        if [ -f "$p" ]; then
            SQL_FILE="$p"
            break
        fi
    done
    
    if [ -z "$SQL_FILE" ]; then
        if [ $# -ge 1 ] && [ -f "$1" ]; then
            SQL_FILE="$1"
        else
            echo "❌ 未找到 init-opengauss.sql 文件！"
            echo "请将 init-opengauss.sql 放在当前目录或通过参数指定：$0 opengauss /path/to/init-opengauss.sql"
            exit 1
        fi
    fi
    
    echo "=========================================="
    echo "准备导入 openGauss 数据库脚本: $SQL_FILE"
    echo "目标容器: $CONTAINER_NAME | 数据库: $DB_NAME"
    echo "=========================================="
    
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "❌ 容器 ${CONTAINER_NAME} 未运行，请先执行部署脚本"
        exit 1
    fi
    
    echo "正在检测 openGauss 服务连通性..."
    MAX_RETRIES=30
    RETRY_COUNT=0
    until docker exec -i "${CONTAINER_NAME}" su - omm -c "source ~/.bashrc; gsql -d ${DB_NAME} -c '\q'" >/dev/null 2>&1; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "❌ openGauss 服务响应超时，请检查容器状态与日志！"
            exit 1
        fi
        echo "等待 openGauss 启动就绪 ($RETRY_COUNT/$MAX_RETRIES)..."
        sleep 2
    done
    echo "✅ openGauss 服务正常运行"
    
    docker exec -i "${CONTAINER_NAME}" su - omm -c "source ~/.bashrc; gsql -d ${DB_NAME} -c 'CREATE SCHEMA IF NOT EXISTS gaussdb AUTHORIZATION ${DB_USER};'" >/dev/null 2>&1 || true
    
    echo "正在导入 SQL 脚本中，请稍候..."
    if docker exec -i "${CONTAINER_NAME}" su - omm -c "source ~/.bashrc; gsql -d ${DB_NAME} -U ${DB_USER} -W '${DB_PASS}'" < "$SQL_FILE"; then
        echo "✅ 使用用户 ${DB_USER} 导入完成！"
    else
        echo "⚠️ 使用 ${DB_USER} 遇到权限限制，尝试使用超级管理员 omm 导入..."
        docker exec -i "${CONTAINER_NAME}" su - omm -c "source ~/.bashrc; gsql -d ${DB_NAME}" < "$SQL_FILE"
        echo "✅ 超级管理员 omm 导入完成！"
    fi
    echo "🎉 init-opengauss.sql 数据库初始化成功！"
fi
