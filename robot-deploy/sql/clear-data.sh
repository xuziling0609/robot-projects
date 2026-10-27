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
# 检查是否通过参数传入
if [ -n "${1:-}" ]; then
    case "$1" in
        1|opengauss|openGauss)
            CHOSEN_DB="opengauss"
            ;;
        2|mysql|MySQL)
            CHOSEN_DB="mysql"
            ;;
    esac
fi

if [ -z "${CHOSEN_DB}" ]; then
    CURRENT_CONFIGURED="${DB_TYPE:-opengauss}"
    echo "===================================================="
    echo "请选择要清空数据的数据库引擎 (Clear Data):"
    echo "  1) openGauss"
    echo "  2) MySQL"
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

echo "===================================================="
echo "⚠️  警告：此操作将彻底清空 ${CHOSEN_DB} 中的所有业务数据！"
echo "操作不可逆转，请确保已经做好数据备份。"
echo "===================================================="
read -r -p "确定要继续清空数据吗？[y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消操作。"
    exit 0
fi

if [ "${CHOSEN_DB}" = "mysql" ]; then
    CONTAINER_NAME="app-mysql"
    DB_NAME="${DB_NAME:-robot}"
    DB_USER="root"
    DB_PASS="${MYSQL_PASSWORD:-CHANGE_ME}"
    
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "❌ 容器 ${CONTAINER_NAME} 未运行，无法连接数据库执行清空操作"
        exit 1
    fi
    
    echo "正在清空 MySQL 数据库: ${DB_NAME} ..."
    if docker exec -i "${CONTAINER_NAME}" mysql -u"${DB_USER}" -p"${DB_PASS}" -e "DROP DATABASE IF EXISTS \`${DB_NAME}\`; CREATE DATABASE \`${DB_NAME}\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"; then
        echo "✅ MySQL 数据库 ${DB_NAME} 数据已清空 (数据库已重建)！"
    else
        echo "❌ 清空数据失败，请检查数据库服务状态。"
        exit 1
    fi

elif [ "${CHOSEN_DB}" = "opengauss" ]; then
    CONTAINER_NAME="app-opengauss"
    DB_NAME="postgres"
    DB_USER="gaussdb"
    DB_PASS="${OPENGAUSS_PASSWORD:-CHANGE_ME}"
    
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "❌ 容器 ${CONTAINER_NAME} 未运行，无法连接数据库执行清空操作"
        exit 1
    fi
    
    echo "正在清空 openGauss 业务 Schema: ${DB_USER} ..."
    # 通过超级管理员删除 schema 及其下属所有表
    if docker exec -i "${CONTAINER_NAME}" su - omm -c "source ~/.bashrc; gsql -d ${DB_NAME} -c 'DROP SCHEMA IF EXISTS ${DB_USER} CASCADE;'"; then
        # 重新创建空的 Schema
        docker exec -i "${CONTAINER_NAME}" su - omm -c "source ~/.bashrc; gsql -d ${DB_NAME} -c 'CREATE SCHEMA IF NOT EXISTS ${DB_USER} AUTHORIZATION ${DB_USER};'" >/dev/null 2>&1 || true
        echo "✅ openGauss 业务架构 ${DB_USER} 数据已清空！"
    else
        echo "❌ 清空数据失败，请检查数据库服务状态。"
        exit 1
    fi
fi
