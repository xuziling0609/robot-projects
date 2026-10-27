# 智能机器人平台 - SSL/TLS 证书一键生成套件

本项目提供了基于 `mkcert` 的全自动本地/局域网 SSL 证书签发工具，已预置适配主流架构的二进制程序，支持一键自适应生成高可信的本地 SSL/TLS 证书。

---

## 一、 文件组织结构

```text
ssl/
├── bin/
│   ├── mkcert-v1.4.4-linux-amd64    # x86_64 / amd64 平台专用二进制
│   └── mkcert-v1.4.4-linux-arm64    # aarch64 / arm64 (麒麟/飞腾/鲲鹏) 专用二进制
├── ssl.sh                           # 一键 SSL/HTTPS 管理与证书生成脚本
├── cert/                            # 生成的证书目录 (服务证书 + 本地根证书)
│   ├── server.crt                   # 服务器公钥证书 (对应 Nginx ssl_certificate)
│   ├── server.key                   # 服务器私钥文件 (对应 Nginx ssl_certificate_key，权限: 600)
│   ├── rootca.crt                   # 导出的受信任本地根证书 (供客户端电脑/手机导入)
│   ├── rootCA.pem                   # 根证书源文件
│   └── rootCA-key.pem               # 根证书私钥
└── README.md                        # 使用与排障文档
```

---

## 二、 核心功能与运行机制

1. **多架构自动识别**：
   - 脚本通过 `uname -m` 自动识别系统硬件架构（`amd64` 或 `arm64`）；
   - 自动匹配并赋予 `ssl/bin/` 对应二进制文件的执行权限，无需用户手动区分。
2. **IP 与域名智能发现**：
   - 默认自动包含 `localhost`、`127.0.0.1`、`::1`；
   - 自动探测服务器本机主网卡内网 IP（如 `192.168.x.x`）；
   - 支持命令行追加自定义域名或外部 IP。
3. **自动同步与容器挂载联动**：
   - 证书生成后，自动同步至 **`app-init/nginx/cert/`** 模板目录；
   - 同时读取项目根目录 `.env` 中的 `DATA_DIR`（默认为 `/home/zonwey/robot/app`），自动同步至宿主机实际挂载目录 **`${DATA_DIR}/nginx/cert`**；
   - 无论是执行 `./2-chmod.sh` 首次部署初始化，还是在部署后重新生成证书，均能无缝自动对接；
   - 每次操作完成后，自动重启 Nginx 网关容器，使配置与证书立即生效。

---

## 三、 使用说明

### 1. 交互式菜单运行 (推荐)

直接执行脚本，将提供交互菜单供选择**开启**或**关闭** SSL：

```bash
./ssl/ssl.sh
```

- **选项 1) 开启 SSL**：自动签发 `server.crt` 与 `server.key`，将 `ssl/conf/default-ssl.conf` 复制为 `app-init/nginx/conf/default.conf`，同步证书至 `app-init/nginx/cert/` 和挂载目录，并自动重启 Nginx 生效。
- **选项 2) 关闭 SSL**：将 `ssl/conf/default.conf` 复制为 `app-init/nginx/conf/default.conf`，清空 `app-init/nginx/cert/` 中的证书，并自动重启 Nginx 生效。

### 2. 命令行免交互快捷调用

```bash
# 一键开启 SSL (使用本机 IP 与 localhost 签发并重启 Nginx)
./ssl/ssl.sh on
# 或
./ssl/ssl.sh 1

# 开启 SSL 并追加指定局域网域名与其它 IP
./ssl/ssl.sh on 192.168.1.100 robot.local admin.robot.lan

# 一键关闭 SSL (还原 HTTP 配置、清空证书并重启 Nginx)
./ssl/ssl.sh off
# 或
./ssl/ssl.sh 2
```

### 3. 可选：将 CA 注册到当前宿主机系统证书库

若需让当前 Linux 宿主机的命令行（如 `curl`、`wget`、Docker）直接信任该证书：

```bash
sudo bash ssl/ssl.sh --install
```

---

## 四、 客户端消除“不安全”警告（安装根证书）

生成的证书是基于本地专用 Root CA 签发的。如需让访问管理平台的客户端电脑（Windows / Mac）或移动设备（Chrome / Edge）显示“安全小绿锁”：

1. **获取根证书文件**：
   - **方式 A (浏览器直链下载，推荐)**：访问 `http://<服务器IP>/rootca.crt`，HTTP 协议不校验 SSL，可直接免告警下载根证书文件；亦可通过 `https://<服务器IP>/rootca.crt` 下载（首次若提示“证书不安全/非私密连接”，点击“高级” -> “继续前往”即可触发下载）。
   - **方式 B (服务端直接拷贝)**：从服务端的 `ssl/cert/rootca.crt` 或 `app-init/nginx/cert/rootca.crt` 拷贝到客户端设备。
2. **Windows 客户端导入**：
   - 双击 `rootca.crt` 文件 -> 点击 **“安装证书”**；
   - 存储位置选择 **“当前用户”** 或 **“本地计算机”**；
   - 选择 **“将所有的证书都放入下列存储”** -> 点击 **“浏览”** -> 选中 **“受信任的根证书颁发机构”**；
   - 一路点击“下一步”直到完成导入；
   - 完全重启浏览器，访问 `https://<服务器IP>` 即可无警告安全访问。
3. **macOS 客户端导入**：
   - 双击 `rootca.crt` 导入 **钥匙串访问 (Keychain Access)**；
   - 在“系统”或“登录”分类中找到刚刚导入的 `mkcert development CA`；
   - 双击打开，展开 **“信任”** 栏，将“使用此证书时”下拉框修改为 **“始终信任”**；
   - 关闭窗口并输入电脑开机密码保存，重启浏览器即可。
