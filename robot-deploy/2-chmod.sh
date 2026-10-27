#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. 读取 .env 配置
if [ -f .env ]; then
    # shellcheck disable=SC1091
    source .env
fi

TARGET_DIR="${DATA_DIR:-/home/app}"
INIT_DIR="${SCRIPT_DIR}/app-init"

echo "=========================================="
echo "检查与初始化数据挂载目录: ${TARGET_DIR}"
echo "=========================================="

# 2. 确保目标根目录存在
if [ ! -d "${TARGET_DIR}" ]; then
    echo "创建目标根目录: ${TARGET_DIR} ..."
    mkdir -p "${TARGET_DIR}" 2>/dev/null || sudo mkdir -p "${TARGET_DIR}"
fi

# 3. 检查并从 app-init 复制所需文件夹与文件
if [ -d "${INIT_DIR}" ]; then
    echo "正在校验业务必要文件夹及初始配置..."
    for item in "${INIT_DIR}"/*; do
        [ -e "$item" ] || continue
        base_name="$(basename "$item")"
        dest_item="${TARGET_DIR}/${base_name}"

        if [ "${base_name}" = "nginx" ]; then
            # 针对 nginx 特殊处理：每次强制覆盖配置与前端资源，不拷贝 dist.tar.gz 压缩包
            echo "  -> 正在覆盖同步 [nginx] 配置及静态资源..."
            mkdir -p "${dest_item}" 2>/dev/null || sudo mkdir -p "${dest_item}"

            # 覆盖复制除 dist.tar.gz 以外的子项（如 conf/、nginx.conf 等）
            for sub_item in "${item}"/*; do
                [ -e "${sub_item}" ] || continue
                sub_name="$(basename "${sub_item}")"
                # 跳过 dist.tar.gz 压缩包，避免拷贝到挂载目录
                if [ "${sub_name}" = "dist.tar.gz" ]; then
                    continue
                fi

                sub_dest="${dest_item}/${sub_name}"
                if [ -d "${sub_item}" ]; then
                    mkdir -p "${sub_dest}" 2>/dev/null || sudo mkdir -p "${sub_dest}"
                    cp -a "${sub_item}/." "${sub_dest}/" 2>/dev/null || sudo cp -a "${sub_item}/." "${sub_dest}/"
                else
                    cp -a "${sub_item}" "${dest_item}/" 2>/dev/null || sudo cp -a "${sub_item}" "${dest_item}/"
                fi
            done

            # 清理目标目录中可能残留的 dist.tar.gz
            if [ -f "${dest_item}/dist.tar.gz" ]; then
                rm -f "${dest_item}/dist.tar.gz" 2>/dev/null || sudo rm -f "${dest_item}/dist.tar.gz" 2>/dev/null || true
            fi

            # 每次强制覆盖解压 dist.tar.gz 到目标目录（解压出 dist/）
            if [ -f "${item}/dist.tar.gz" ]; then
                echo "  -> 每次覆盖解压前端静态资源包 [dist.tar.gz] 到 ${dest_item}/ ..."
                tar -zxf "${item}/dist.tar.gz" -C "${dest_item}" 2>/dev/null || sudo tar -zxf "${item}/dist.tar.gz" -C "${dest_item}"
            fi

        elif [ "${base_name}" = "jars" ] || [ "${base_name}" = "jar" ]; then
            # 针对 jars 特殊处理：每次强制覆盖构建上下文及后端核心包 (Dockerfile、Jar包、application配置等)
            echo "  -> 正在覆盖同步 [${base_name}] 核心包与配置文件..."
            mkdir -p "${dest_item}" 2>/dev/null || sudo mkdir -p "${dest_item}"
            cp -a "${item}/." "${dest_item}/" 2>/dev/null || sudo cp -a "${item}/." "${dest_item}/"

        else
            # 其他服务（如 emqx、go2rtc 等）：缺失时初始化，已存在则增量保护不覆盖
            if [ ! -e "${dest_item}" ]; then
                echo "  -> 发现缺失 [${base_name}]，正在从 app-init 初始化复制..."
                cp -a "${item}" "${TARGET_DIR}/" 2>/dev/null || sudo cp -a "${item}" "${TARGET_DIR}/"
            else
                if [ -d "${item}" ]; then
                    cp -an "${item}/." "${dest_item}/" 2>/dev/null || sudo cp -an "${item}/." "${dest_item}/" 2>/dev/null || true
                fi
            fi
        fi
    done
else
    echo "⚠️ 未检测到 app-init 初始化目录，跳过模板文件复制"
fi

# 4. 补充数据库、对象存储、Java 及 Nginx 必要子目录
mkdir -p "${TARGET_DIR}/mysql/data" 2>/dev/null || sudo mkdir -p "${TARGET_DIR}/mysql/data" 2>/dev/null || true
mkdir -p "${TARGET_DIR}/seaweedfs/data" 2>/dev/null || sudo mkdir -p "${TARGET_DIR}/seaweedfs/data" 2>/dev/null || true
mkdir -p "${TARGET_DIR}/redis/data" 2>/dev/null || sudo mkdir -p "${TARGET_DIR}/redis/data" 2>/dev/null || true
mkdir -p "${TARGET_DIR}/jars/logs" 2>/dev/null || sudo mkdir -p "${TARGET_DIR}/jars/logs" 2>/dev/null || true
mkdir -p "${TARGET_DIR}/jars/upload" 2>/dev/null || sudo mkdir -p "${TARGET_DIR}/jars/upload" 2>/dev/null || true
mkdir -p "${TARGET_DIR}/jars/config" 2>/dev/null || sudo mkdir -p "${TARGET_DIR}/jars/config" 2>/dev/null || true
mkdir -p "${TARGET_DIR}/nginx/logs" 2>/dev/null || sudo mkdir -p "${TARGET_DIR}/nginx/logs" 2>/dev/null || true
mkdir -p "${TARGET_DIR}/nginx/cert" 2>/dev/null || sudo mkdir -p "${TARGET_DIR}/nginx/cert" 2>/dev/null || true

# 5. 配置目录读写权限
echo "配置目录权限: ${TARGET_DIR} (777) ..."
chmod -R 777 "${TARGET_DIR}" 2>/dev/null || sudo chmod -R 777 "${TARGET_DIR}" 2>/dev/null || true

echo "✅ 挂载目录初始化与权限配置完成！"