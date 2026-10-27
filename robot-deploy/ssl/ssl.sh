#!/bin/bash
# ==============================================================================
# 智能机器人综合管理平台 - 一键 SSL/HTTPS 管理与自适应证书生成脚本
# 支持架构: x86_64 (amd64) / aarch64 (arm64)
# 功能说明: 
#   1. [开启 SSL]: 自动选择架构匹配的 mkcert 二进制签发 server.crt / server.key，
#      将 default-ssl.conf 复制为 app-init/nginx/conf/default.conf，
#      并将 server.crt / server.key / rootca.crt 统一同步至 app-init/nginx/cert/；
#   2. [关闭 SSL]: 将 default.conf 还原至 app-init/nginx/conf/default.conf，
#      并彻底清空 app-init/nginx/cert/ 目录。
# ==============================================================================

set -euo pipefail

# 脚本所在目录及工程根目录
SSL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SSL_DIR}/.." && pwd)"

# 加载部署根目录下的 .env 环境变量
if [ -f "${DEPLOY_DIR}/.env" ]; then
    # shellcheck disable=SC1091
    source "${DEPLOY_DIR}/.env"
fi

# 核心路径定义
SSL_CONF_DIR="${SSL_DIR}/conf"
SSL_OUT_DIR="${SSL_DIR}/cert"

APP_INIT_CONF="${DEPLOY_DIR}/app-init/nginx/conf/default.conf"
APP_INIT_CERT_DIR="${DEPLOY_DIR}/app-init/nginx/cert"

TARGET_DATA_DIR="${DATA_DIR:-/home/zonwey/robot/app}"
NGINX_CONF="${TARGET_DATA_DIR}/nginx/conf/default.conf"
NGINX_CERT_DIR="${TARGET_DATA_DIR}/nginx/cert"

INSTALL_TO_SYSTEM=false
ACTION=""
CUSTOM_ARGS=()

# 解析命令行参数
for arg in "$@"; do
    case "$arg" in
        1|on|enable|open|[yY][eE][sS])
            if [ -z "${ACTION}" ]; then ACTION="enable"; continue; fi
            ;;
        2|off|disable|close|[nN][oO])
            if [ -z "${ACTION}" ]; then ACTION="disable"; continue; fi
            ;;
        --install|--install-ca)
            INSTALL_TO_SYSTEM=true
            continue
            ;;
        -h|--help)
            echo "用法: $0 [1|2|on|off] [选项] [域名/IP 列表...]"
            echo
            echo "操作选项:"
            echo "  1, on, enable              开启 SSL (签发证书，复制 default-ssl.conf 到 app-init，部署证书至 cert)"
            echo "  2, off, disable            关闭 SSL (还原 default.conf 到 app-init，并清空证书目录)"
            echo "  --install, --install-ca    尝试将 CA 证书安装到当前操作系统受信任库 (可能需 sudo)"
            echo "  -h, --help                 显示帮助信息"
            echo
            echo "示例:"
            echo "  $0                         # 交互菜单选择开启或关闭 SSL"
            echo "  $0 on                      # 直接开启 SSL (默认本机 IP 与 localhost)"
            echo "  $0 on 192.168.1.100 robot  # 开启 SSL 并追加指定 IP 与域名"
            echo "  $0 off                     # 关闭 SSL，还原 HTTP 配置并清空证书"
            exit 0
            ;;
    esac
    CUSTOM_ARGS+=("$arg")
done

# 若首个非选项参数不是 on/off，但有其他参数（如 IP/域名），默认进入开启逻辑
if [ -z "${ACTION}" ] && [ ${#CUSTOM_ARGS[@]} -gt 0 ]; then
    ACTION="enable"
fi

IS_INTERACTIVE=false
# 交互式选择 (未指定参数且处于交互终端时)
if [ -z "${ACTION}" ]; then
    IS_INTERACTIVE=true
    echo "===================================================="
    echo "      智能机器人综合管理平台 - SSL/HTTPS 配置管理"
    echo "===================================================="
    echo "请选择要执行的操作:"
    echo "  1) 开启 SSL (自动签发证书，应用 HTTPS 配置并部署下载路由) [默认]"
    echo "  2) 关闭 SSL (恢复 HTTP 基础配置，并清空证书目录)"
    echo "===================================================="
    
    input_choice=""
    if [ -t 0 ]; then
        if read -r -t 15 -p "请输入选项序号 [1/2] (默认: 1): " input_choice; then
            :
        else
            echo -e "\n⏰ 超时未输入，默认执行 [1] 开启 SSL..."
            input_choice="1"
        fi
    else
        input_choice="1"
    fi

    case "${input_choice}" in
        2|off|disable|close|[nN][oO])
            ACTION="disable"
            ;;
        1|on|enable|open|[yY][eE][sS]|"")
            ACTION="enable"
            ;;
        *)
            echo "⚠️ 输入无效，默认执行 [1] 开启 SSL..."
            ACTION="enable"
            ;;
    esac
fi

# 重启 Nginx 容器以使配置和证书立即生效
restart_nginx() {
    echo
    echo "🔄 正在重启 Nginx 网关容器以立即应用配置..."
    if [ -f "${DEPLOY_DIR}/6-restart.sh" ]; then
        bash "${DEPLOY_DIR}/6-restart.sh" nginx || true
    elif command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^app-nginx$'; then
        docker restart app-nginx 2>/dev/null || true
        echo "✅ app-nginx 重启完成"
    else
        echo "⚠️ 未检测到运行中的 Nginx 容器，待启动后自动生效"
    fi
}

# ==============================================================================
# 模式 A: 关闭 SSL
# ==============================================================================
if [ "${ACTION}" = "disable" ]; then
    echo
    echo "===================================================="
    echo "               正在执行：关闭 SSL"
    echo "===================================================="

    # 1. 还原 default.conf 到 app-init
    if [ -f "${SSL_CONF_DIR}/default.conf" ]; then
        echo "📝 正在复制 HTTP 配置 [default.conf] 到 ${APP_INIT_CONF} ..."
        mkdir -p "$(dirname "${APP_INIT_CONF}")"
        cp -f "${SSL_CONF_DIR}/default.conf" "${APP_INIT_CONF}"
        echo "✅ app-init 配置文件已还原为 HTTP 模式"
    else
        echo "⚠️ 未找到模板源文件: ${SSL_CONF_DIR}/default.conf"
    fi

    # 2. 同步还原至宿主机挂载目录（如果存在）
    if [ -f "${NGINX_CONF}" ] || [ -d "$(dirname "${NGINX_CONF}")" ]; then
        echo "📝 正在同步 HTTP 配置至 Nginx 挂载目录: ${NGINX_CONF} ..."
        cp -f "${SSL_CONF_DIR}/default.conf" "${NGINX_CONF}" 2>/dev/null || sudo -n cp -f "${SSL_CONF_DIR}/default.conf" "${NGINX_CONF}" 2>/dev/null || true
        echo "✅ Nginx 挂载目录配置已还原为 HTTP 模式"
    fi

    # 3. 清空 app-init/nginx/cert/ 证书文件 (不保留 .gitkeep)
    echo "🧹 正在清空 app-init 证书目录: ${APP_INIT_CERT_DIR} ..."
    if [ -d "${APP_INIT_CERT_DIR}" ]; then
        find "${APP_INIT_CERT_DIR}" -mindepth 1 -delete 2>/dev/null || true
        echo "✅ 已清空 app-init 证书目录"
    fi

    # 4. 清空宿主机挂载证书目录
    if [ -d "${NGINX_CERT_DIR}" ]; then
        echo "🧹 正在清空 Nginx 挂载证书目录: ${NGINX_CERT_DIR} ..."
        find "${NGINX_CERT_DIR}" -mindepth 1 -delete 2>/dev/null || sudo -n find "${NGINX_CERT_DIR}" -mindepth 1 -delete 2>/dev/null || true
        echo "✅ 已清空 Nginx 挂载证书目录"
    fi

    # 5. 清理 ssl/cert/ 目录中的服务端证书 (保留根证书 rootCA.pem / rootCA-key.pem / rootca.crt)
    if [ -d "${SSL_OUT_DIR}" ]; then
        rm -f "${SSL_OUT_DIR}"/server.crt "${SSL_OUT_DIR}"/server.key "${SSL_OUT_DIR}"/server.pem "${SSL_OUT_DIR}"/cert.* "${SSL_OUT_DIR}"/key.* 2>/dev/null || true
    fi

    echo
    echo "========================================================================"
    echo "🛑 SSL 已成功关闭！"
    echo "========================================================================"
    echo "1. HTTP 配置已还原: ${APP_INIT_CONF}"
    if [ -f "${NGINX_CONF}" ]; then
        echo "   - 挂载路径: ${NGINX_CONF}"
    fi
    echo "2. 证书目录已清空: ${APP_INIT_CERT_DIR}"
    if [ -d "${NGINX_CERT_DIR}" ]; then
        echo "   - 挂载证书: ${NGINX_CERT_DIR}"
    fi
    echo "========================================================================"
    restart_nginx
    exit 0
fi

# ==============================================================================
# 模式 B: 开启 SSL
# ==============================================================================
echo
echo "===================================================="
echo "               正在执行：开启 SSL"
echo "===================================================="

# 1. 自动检测系统平台与 CPU 架构，选取二进制文件
detect_binary() {
    local os_type arch_type
    os_type="$(uname -s | tr '[:upper:]' '[:lower:]')"
    arch_type="$(uname -m)"

    if [ "${os_type}" != "linux" ]; then
        echo "❌ 当前仅支持 Linux 操作系统 (检测到: ${os_type})"
        exit 1
    fi

    case "${arch_type}" in
        x86_64|amd64)
            MKCERT_BIN="${SSL_DIR}/bin/mkcert-v1.4.4-linux-amd64"
            echo "✅ 检测到系统架构: x86_64 / amd64"
            ;;
        aarch64|arm64)
            MKCERT_BIN="${SSL_DIR}/bin/mkcert-v1.4.4-linux-arm64"
            echo "✅ 检测到系统架构: aarch64 / arm64"
            ;;
        *)
            echo "❌ 不支持的系统架构: ${arch_type}"
            echo "   当前预置二进制仅支持: x86_64 (amd64) 与 aarch64 (arm64)"
            exit 1
            ;;
    esac

    if [ ! -f "${MKCERT_BIN}" ]; then
        echo "❌ 未找到对应架构的 mkcert 二进制文件: ${MKCERT_BIN}"
        exit 1
    fi

    # 确保执行权限
    if [ ! -x "${MKCERT_BIN}" ]; then
        echo "🔧 赋予 mkcert 可执行权限..."
        chmod +x "${MKCERT_BIN}" 2>/dev/null || sudo -n chmod +x "${MKCERT_BIN}" 2>/dev/null || true
    fi

    echo "🚀 匹配二进制工具: $(basename "${MKCERT_BIN}")"
}

MKCERT_BIN=""
detect_binary

# 2. 自动检测本机主要 IP 地址
detect_local_ip() {
    LOCAL_IP=""
    DETECTED_IPS=()
    if command -v ip >/dev/null 2>&1; then
        while IFS= read -r ip_val; do
            if [ -n "${ip_val}" ] && [ "${ip_val}" != "127.0.0.1" ]; then
                DETECTED_IPS+=("${ip_val}")
            fi
        done < <(ip -4 addr show scope global 2>/dev/null | grep -v 'docker\|br-\|veth\|10\.255\.' | awk '/inet / {print $2}' | cut -d/ -f1 || true)
    fi

    # 优先选取 192.168.x.x 局域网物理网段
    for ip_cand in "${DETECTED_IPS[@]}"; do
        if [[ "${ip_cand}" =~ ^192\.168\. ]]; then
            LOCAL_IP="${ip_cand}"
            break
        fi
    done

    # 其次选取首个检测到的有效 IP (排除 10.255.* 虚拟网段)
    if [ -z "${LOCAL_IP}" ]; then
        for ip_cand in "${DETECTED_IPS[@]}"; do
            if [[ ! "${ip_cand}" =~ ^10\.255\. ]]; then
                LOCAL_IP="${ip_cand}"
                break
            fi
        done
    fi

    if [ -z "${LOCAL_IP}" ]; then
        LOCAL_IP="127.0.0.1"
    fi
}

LOCAL_IP=""
DETECTED_IPS=()
detect_local_ip

# 3. 收集证书签发域名 / IP 列表 (默认仅包含本机环回与实际物理局域网 IP)
RAW_DOMAINS=("localhost" "127.0.0.1" "::1")
if [ -n "${LOCAL_IP}" ] && [ "${LOCAL_IP}" != "127.0.0.1" ] && [[ ! "${LOCAL_IP}" =~ ^10\.255\. ]]; then
    RAW_DOMAINS+=("${LOCAL_IP}")
fi

DOMAINS=()
while IFS= read -r line; do
    [ -n "$line" ] && DOMAINS+=("$line")
done < <(printf '%s\n' "${RAW_DOMAINS[@]}" | sort -u)

if [ ${#CUSTOM_ARGS[@]} -gt 0 ]; then
    for arg in "${CUSTOM_ARGS[@]}"; do
        DOMAINS+=("${arg}")
    done
elif [ "${IS_INTERACTIVE}" = "true" ] && [ -t 0 ]; then
    echo
    echo "当前自动规划签发的主机/IP:"
    for d in "${DOMAINS[@]}"; do
        echo "  - $d"
    done
    echo
    extra_inputs=""
    if read -r -t 15 -p "如需追加更多域名或外部IP（空格分隔，直接回车使用默认值）: " extra_inputs; then
        :
    else
        echo -e "\n⏰ 超时未输入，默认使用当前 IP 与主机名继续..."
    fi
    if [ -n "${extra_inputs}" ]; then
        for item in ${extra_inputs}; do
            DOMAINS+=("${item}")
        done
    fi
fi

UNIQUE_DOMAINS=()
while IFS= read -r line; do
    [ -n "$line" ] && UNIQUE_DOMAINS+=("$line")
done < <(printf '%s\n' "${DOMAINS[@]}" | sort -u)

echo
echo "📜 证书将覆盖以下所有域名与 IP:"
for d in "${UNIQUE_DOMAINS[@]}"; do
    echo "   * $d"
done

# 4. 创建目录并配置本地 Root CA (统一置于 cert 目录)
mkdir -p "${SSL_OUT_DIR}"
export CAROOT="${SSL_OUT_DIR}"

if [ "${INSTALL_TO_SYSTEM}" = "true" ]; then
    echo
    echo "🔐 正在尝试将本地根证书注册至本机受信任根证书库 (若弹出密码请输入 sudo 密码)..."
    "${MKCERT_BIN}" -install || true
fi

# 5. 签发服务器 SSL 证书与私钥 (仅生成 Nginx 部署所需的两个核心文件: server.crt 与 server.key)
SERVER_CRT="${SSL_OUT_DIR}/server.crt"
SERVER_KEY="${SSL_OUT_DIR}/server.key"

echo
echo "🚀 正在使用 mkcert 签发 Nginx 所需证书 (server.crt / server.key)..."
rm -f "${SSL_OUT_DIR}"/cert.* "${SSL_OUT_DIR}"/key.* "${SSL_OUT_DIR}"/server.pem 2>/dev/null || true

"${MKCERT_BIN}" -cert-file "${SERVER_CRT}" -key-file "${SERVER_KEY}" "${UNIQUE_DOMAINS[@]}"

if [ -f "${SSL_OUT_DIR}/rootCA.pem" ]; then
    echo "✅ 根证书已生成: ${SSL_OUT_DIR}/rootCA.pem"
    cp -f "${SSL_OUT_DIR}/rootCA.pem" "${SSL_OUT_DIR}/rootca.crt"
    rm -f "${SSL_OUT_DIR}/rootCA.crt" 2>/dev/null || true
    echo "💡 客户端根证书已就绪: ${SSL_OUT_DIR}/rootca.crt"
fi

rm -f "${SSL_DIR}/rootCA.crt" "${SSL_DIR}/rootca.crt" 2>/dev/null || true
rm -rf "${SSL_DIR}/ca" 2>/dev/null || true

chmod 644 "${SERVER_CRT}" "${SSL_OUT_DIR}"/rootca.crt 2>/dev/null || true
chmod 600 "${SERVER_KEY}" "${SSL_OUT_DIR}"/rootCA-key.pem 2>/dev/null || true

echo "✅ 证书文件已就绪于: ${SSL_OUT_DIR}"

# 6. 复制 default-ssl.conf 内容到 app-init/nginx/conf/default.conf
if [ -f "${SSL_CONF_DIR}/default-ssl.conf" ]; then
    echo
    echo "📝 正在复制 HTTPS 配置 [default-ssl.conf] 到 ${APP_INIT_CONF} ..."
    mkdir -p "$(dirname "${APP_INIT_CONF}")"
    cp -f "${SSL_CONF_DIR}/default-ssl.conf" "${APP_INIT_CONF}"
    echo "✅ 已成功更新 app-init 配置为 HTTPS 模式"
    
    # 同步至宿主机挂载目录（如果存在）
    if [ -f "${NGINX_CONF}" ] || [ -d "$(dirname "${NGINX_CONF}")" ]; then
        echo "📝 正在同步 HTTPS 配置至 Nginx 挂载目录: ${NGINX_CONF} ..."
        cp -f "${SSL_CONF_DIR}/default-ssl.conf" "${NGINX_CONF}" 2>/dev/null || sudo -n cp -f "${SSL_CONF_DIR}/default-ssl.conf" "${NGINX_CONF}" 2>/dev/null || true
        echo "✅ Nginx 挂载目录配置已同步更新为 HTTPS 模式"
    fi
else
    echo "⚠️ 未找到模板源文件: ${SSL_CONF_DIR}/default-ssl.conf"
fi

# 7. 同步证书两件套及 rootca.crt 到 app-init/nginx/cert 目录与 Nginx 实际挂载目录
echo
echo "📦 正在同步证书 (server.crt, server.key, rootca.crt) 到 app-init 目录: ${APP_INIT_CERT_DIR} ..."
mkdir -p "${APP_INIT_CERT_DIR}"
rm -f "${APP_INIT_CERT_DIR}"/cert.* "${APP_INIT_CERT_DIR}"/key.* "${APP_INIT_CERT_DIR}"/server.pem "${APP_INIT_CERT_DIR}"/rootCA.crt 2>/dev/null || true

cp -f "${SERVER_CRT}" "${APP_INIT_CERT_DIR}/server.crt"
cp -f "${SERVER_KEY}" "${APP_INIT_CERT_DIR}/server.key"
if [ -f "${SSL_OUT_DIR}/rootca.crt" ]; then
    cp -f "${SSL_OUT_DIR}/rootca.crt" "${APP_INIT_CERT_DIR}/rootca.crt"
fi

chmod 644 "${APP_INIT_CERT_DIR}"/server.crt "${APP_INIT_CERT_DIR}"/rootca.crt 2>/dev/null || true
chmod 600 "${APP_INIT_CERT_DIR}"/server.key 2>/dev/null || true
echo "✅ 已成功同步证书至: ${APP_INIT_CERT_DIR}"

# 同步至宿主机数据挂载目录
if [ -d "${TARGET_DATA_DIR}" ] || [ -d "${NGINX_CERT_DIR}" ]; then
    echo "📦 正在同步证书到 Nginx 容器挂载目录: ${NGINX_CERT_DIR} ..."
    mkdir -p "${NGINX_CERT_DIR}" 2>/dev/null || sudo -n mkdir -p "${NGINX_CERT_DIR}" 2>/dev/null || true
    if [ -d "${NGINX_CERT_DIR}" ]; then
        rm -f "${NGINX_CERT_DIR}"/cert.* "${NGINX_CERT_DIR}"/key.* "${NGINX_CERT_DIR}"/server.pem "${NGINX_CERT_DIR}"/rootCA.crt 2>/dev/null || sudo -n rm -f "${NGINX_CERT_DIR}"/cert.* "${NGINX_CERT_DIR}"/key.* "${NGINX_CERT_DIR}"/server.pem "${NGINX_CERT_DIR}"/rootCA.crt 2>/dev/null || true
        cp -f "${SERVER_CRT}" "${NGINX_CERT_DIR}/server.crt" 2>/dev/null || sudo -n cp -f "${SERVER_CRT}" "${NGINX_CERT_DIR}/server.crt" 2>/dev/null || true
        cp -f "${SERVER_KEY}" "${NGINX_CERT_DIR}/server.key" 2>/dev/null || sudo -n cp -f "${SERVER_KEY}" "${NGINX_CERT_DIR}/server.key" 2>/dev/null || true
        if [ -f "${SSL_OUT_DIR}/rootca.crt" ]; then
            cp -f "${SSL_OUT_DIR}/rootca.crt" "${NGINX_CERT_DIR}/rootca.crt" 2>/dev/null || sudo -n cp -f "${SSL_OUT_DIR}/rootca.crt" "${NGINX_CERT_DIR}/rootca.crt" 2>/dev/null || true
        fi
        chmod -R 755 "${NGINX_CERT_DIR}" 2>/dev/null || sudo -n chmod -R 755 "${NGINX_CERT_DIR}" 2>/dev/null || true
        echo "✅ 已成功同步证书至: ${NGINX_CERT_DIR}"
    fi
fi

# 8. 完成提示与客户端信任引导
echo
echo "========================================================================"
echo "🎉 SSL 证书与 HTTPS 配置开启完成！"
echo "========================================================================"
echo "📁 1. 证书清单 (统一同步至 ${APP_INIT_CERT_DIR}):"
echo "   - 公钥证书 (ssl_certificate)    : server.crt"
echo "   - 私钥文件 (ssl_certificate_key): server.key"
echo "   - 客户端根证书 (直链下载文件)  : rootca.crt"
echo "📁 2. 配置文件已同步为 HTTPS 模式:"
echo "   - 模板路径: ${APP_INIT_CONF}"
if [ -f "${NGINX_CONF}" ]; then
    echo "   - 挂载路径: ${NGINX_CONF}"
fi
echo
echo "🌐 3. 客户端根证书直接下载路由 (推荐在客户端浏览器/手机直接打开):"
echo "   - HTTP 免跳转直链 (推荐，无证书告警拦截): http://${LOCAL_IP}/rootca.crt"
echo "   - HTTPS 直链 (若提示证书不安全需点击继续前往): https://${LOCAL_IP}/rootca.crt"
echo
echo "💡 4. 客户端安装下载的 rootca.crt 后，访问 https://${LOCAL_IP} 即可点亮小绿锁！"
echo "========================================================================"

# 9. 重启 Nginx 容器以立即生效
restart_nginx
