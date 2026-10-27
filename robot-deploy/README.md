# 智能机器人综合管理平台 - Docker 一键化部署套件

本项目提供了基于 Docker & Docker Compose 的一键化、容器化高可用部署方案。支持 **x86_64 (amd64)** 与 **ARM64 (aarch64)** 双架构，适配国产化操作系统（如 Kylin Linux 银河麒麟、openEuler、CentOS、Ubuntu 等），集成了数据持久化、健康检查依赖链、自动目录初始化与离线镜像自适应加载。

---

## 一、 系统架构与组件清单

```
                       ┌──────────────────────────────┐
                       │     Nginx (反向代理/前端)     │ :80, :443
                       └──────────────┬───────────────┘
                                      │ (healthcheck ready)
                       ┌──────────────▼───────────────┐
                       │       Java 后端应用服务       │ :8080 (内部: 8080/8081)
                       └──────────────┬───────────────┘
                                      │ (healthcheck ready)
         ┌──────────────────┬─────────┴────────┬──────────────────┐
         │                  │                  │                  │
┌────────▼────────┐ ┌───────▼────────┐ ┌───────▼────────┐ ┌───────▼────────┐
│  openGauss 6.0  │ │   Redis 7.4    │ │    EMQX 5.8    │ │   SeaweedFS    │
│    (国产数据库)   │ │    (高速缓存)   │ │   (MQTT消息)   │ │   (对象/文件存储) │
│     :5432       │ │     :6379      │ │  :1883, :18083 │ │  :9333, :8888  │
└─────────────────┘ └────────────────┘ └────────────────┘ └────────────────┘
                                                                  │
                                                        ┌─────────▼────────┐
                                                        │   go2rtc (流媒体) │
                                                        │ :1984, :8554/8555│
                                                        └──────────────────┘
```

### 服务组件版本与说明

| 服务名 | 容器名称 | 基础镜像 | 宿主机端口 | 内部端口 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **openGauss** | `app-opengauss` | `enmotech/opengauss:6.0.0` | `5432` | 5432 | 国产关系型数据库（配置 4GB 共享内存，可选） |
| **MySQL** | `app-mysql` | `mysql:8.0.46` | `3306` | 3306 | 主流开源关系型数据库（UTF8MB4，可选） |
| **Redis** | `app-redis` | `redis:7.4.9` | `6379` | 6379 | 缓存中间件（持久化 AOF + 密码保护） |
| **EMQX** | `app-emqx` | `emqx/emqx:5.8.9` | `1883` / `18083` | 1883 / 18083 | 物联网 MQTT 消息接入代理与控制台 |
| **SeaweedFS** | `app-seaweedfs` | `chrislusf/seaweedfs:latest` | `9333` / `8085` / `8888` | 9333 / 8080 / 8888 | 分布式对象存储与文件系统（启动自动建桶） |
| **go2rtc** | `app-go2rtc` | `alexxit/go2rtc:latest` | `1984` / `8554` / `8555` | 1984 / 8554 / 8555 | RTSP / WebRTC / MSE 视频流网关服务 |
| **Java 后端** | `app-java` | `amazoncorretto:21.0.11` | `8080` | 8080 (或 8081) | 机器人平台 Spring Boot 业务核心 |
| **Nginx** | `app-nginx` | `nginx:1.30.0` | `80` / `443` | 80 / 443 | Web 前端静态资源托管与反向代理入口 |

---

## 二、 目录与文件组织结构

```
/home/deploy/              # 部署项目工程根目录
├── .env                          # 环境变量配置文件（统一配置端口、密码、镜像、数据根目录、选定数据库）
├── docker-compose.yml            # Docker 编排主配置文件（含多Profile数据库、双架构服务）
├── 0-setup-docker.sh            # [0] Docker 环境全自动检测、版本修正(24.0.9)、数据目录迁移确认与免sudo配置
├── uninstall_docker.sh          # Docker & Docker Compose 一键安全完全卸载与环境清理脚本
├── 1-check-env.sh                # [1] 环境检测脚本（架构判断、Docker验证、端口防冲突检测）
├── 2-chmod.sh                    # [2] 挂载目录与权限初始化脚本（自动从 app-init 复制所需文件夹并安全赋权）
├── 3-deploy.sh                   # [3] 一键部署脚本（交互选择数据库、自动建网、离线导包、全量容器拉起）
├── 4-start.sh                    # [4] 启动脚本（支持交互菜单选择启动全部或指定单个容器）
├── 5-stop.sh                     # [5] 停止脚本（支持交互菜单选择停止全部或指定单个容器）
├── 6-restart.sh                  # [6] 重启脚本（支持交互菜单选择重启全部或指定单个容器）
├── app-init/                     # 业务持久化与模板初始目录（用于首次部署自动初始化同步）
│   ├── jars/                     # Java 后端启动包 (robot-admin.jar)、核心配置与 Dockerfile
│   ├── nginx/                    # Nginx 配置文件 (nginx.conf)、各站点配置与前端编译包 (dist/)
│   ├── emqx/                     # EMQX MQTT 代理配置文件 (etc/emqx.conf) 与运行时目录
│   ├── go2rtc/                   # go2rtc 视频流网关配置文件 (go2rtc.yaml)
│   ├── redis/                    # Redis 缓存持久化目录模板
│   ├── seaweedfs/                # SeaweedFS 对象存储目录模板
│   └── opengauss/                # openGauss 初始目录模板
├── sql/                          # 数据库初始化与流式导入脚本
│   ├── init-opengauss.sql        # openGauss 数据库初始结构与种子数据 SQL
│   ├── init-mysql.sql            # MySQL 8.0 数据库初始结构与种子数据 SQL
│   ├── import-sql.sh             # 交互式统一流式导入脚本（自动适配引擎与就绪等待）
│   └── clear-data.sh             # 交互式清空业务数据脚本（用于一键重置环境）
├── docker/                       # Docker & Docker Compose 离线安装二进制包目录
│   ├── download.sh               # 基于 SeaweedFS Filer 接口动态获取文件列表，交互式勾选下载
│   ├── docker-24.0.9-aarch64.tgz
│   ├── docker-24.0.9-x86_64.tgz
│   ├── docker-compose-linux-aarch64
│   └── docker-compose-linux-x86_64
├── docker-image/                 # 离线镜像存放目录（包含 amd64 与 arm64 全量离线包，部署脚本自适应匹配）
    ├── download.sh               # 基于 SeaweedFS Filer 接口动态获取离线镜像列表，交互式勾选下载
    ├── amazoncorretto-21.0.11-amd64.tar
    ├── amazoncorretto-21.0.11-arm64.tar
    ├── emqx-5.8.9-amd64.tar
    ├── emqx-5.8.9-arm64.tar
    ├── go2rtc-1.9.14-amd64.tar
    ├── go2rtc-1.9.14-arm64.tar
    ├── mysql-8.0.46-amd64.tar
    ├── mysql-8.0.46-arm64.tar
    ├── nginx-1.30.0-amd64.tar
    ├── nginx-1.30.0-arm64.tar
    ├── opengauss-6.0.0-amd64.tar
    ├── opengauss-6.0.0-arm64.tar
    ├── redis-7.4.9-amd64.tar
    ├── redis-7.4.9-arm64.tar
    ├── seaweedfs-4.47.0-amd64.tar
    └── seaweedfs-4.47.0-arm64.tar
└── ssl/                          # SSL/TLS 证书一键自适应生成与管理套件 (集成 mkcert)
    ├── ssl.sh                    # 一键 SSL/HTTPS 管理与证书生成脚本 (自动重启 Nginx)
    ├── bin/                      # 离线预置二进制 (支持 amd64 与 arm64 麒麟等架构)
    └── cert/                     # 证书目录 (含服务端 server.crt/key 与客户端 rootca.crt)

/home/zonwey/robot/app/            # 宿主机数据持久化与业务挂载根目录（通过 .env 的 DATA_DIR 指定）
├── opengauss/                    # openGauss 数据库物理持久化数据（由容器内 omm 用户 700 保护）
├── mysql/data/                   # MySQL 8.0 数据库持久化数据
├── redis/data/                   # Redis 持久化数据
├── emqx/data/                    # EMQX 运行数据与插件配置
├── emqx/etc/emqx.conf            # EMQX 核心配置
├── nginx/nginx.conf              # Nginx 主配置文件
├── nginx/conf/                   # Nginx 各站点子配置
├── nginx/dist/                   # Web 前端静态打包文件
├── seaweedfs/data/               # SeaweedFS 对象存储物理块
├── go2rtc/config/                # go2rtc 视频流配置文件 (go2rtc.yaml)
└── jars/                         # Java 后端挂载与构建上下文
    ├── Dockerfile                # Java 后端专用构建文件
    ├── robot-admin.jar           # 业务可执行 Jar 包
    ├── application-cususer.yml   # 业务核心配置
    ├── logs/                     # Java 业务运行时日志
    └── upload/                   # 业务本地文件上传目录
```

---

## 三、 快速部署使用指南

### 第一步：修改并确认环境配置文件 (`.env`)

在正式执行部署脚本前，**务必先检查并修改确认 `.env` 中的核心目录与参数**：

1. **核心目录确认**：
   - **`DATA_DIR`**：宿主机数据与挂载根目录，请确认为实际业务路径（如 `DATA_DIR=/home/zonwey/robot/app`）；
   - **`DOCKER_DIR`**：Docker 引擎数据存储目录（如 `DOCKER_DIR=/home/docker`，将在执行 `./0-setup-docker.sh` 时自动创建或迁移）；
2. **端口与密码确认**：按需微调外部暴露端口及各组件密码；
3. **初始化配置与目录**：确认 `.env` 后执行 `./2-chmod.sh`，脚本会自动检查 `${DATA_DIR}`，如果目标目录下缺少所需组件文件夹，会自动从 `app-init/` 完整复制并赋予读写执行权限（777）。

### 第二步：执行一键部署

在部署目录执行：

```bash
cd deploy

# 0. 准备离线资源（若缺少离线安装包或离线镜像，可一键从 NAS 勾选下载）
bash docker/download.sh        # 勾选下载 Docker/Compose 引擎安装包
bash docker-image/download.sh  # 勾选下载各基础服务 Docker 镜像归档包

# 1. 检查本机 Docker 环境（若未安装或版本不匹配，自动卸载并离线安装 24.0.9）
sudo ./0-setup-docker.sh

# 2. 检查数据挂载目录，自动从 app-init 复制所需初始化文件夹并配置文件权限
./2-chmod.sh

# 3. 检查系统架构、Docker 环境及端口防冲突检测
./1-check-env.sh

# 4. 执行一键自动化部署（交互选择 openGauss 或 MySQL，自动加载本地离线镜像并拉起全量容器）
./3-deploy.sh
# 亦可直接传参非交互部署：./3-deploy.sh opengauss 或 ./3-deploy.sh mysql
```

### 第三步：初始化数据库（手动执行）

全部容器拉起成功后，执行统一数据库导入脚本：

```bash
# 执行一键流式导入（将提供交互式菜单选择要导入的数据库，内置服务连通性重试）
./sql/import-sql.sh
```

*(可选)* 直接通过 Docker 命令行手动导入：
- **openGauss 数据库:**
  ```bash
  docker exec -i app-opengauss su - omm -c "source ~/.bashrc; gsql -d postgres" < sql/init-opengauss.sql
  ```
- **MySQL 数据库:**
  ```bash
  docker exec -i app-mysql mysql -uroot -p"${MYSQL_PASSWORD:-CHANGE_ME}" --default-character-set=utf8mb4 < sql/init-mysql.sql
  ```

---

## 四、 平台日常运维管理

部署完成后，日常运维可直接使用根目录下的封装脚本。脚本均已支持**交互式终端菜单**与**命令行免交互快捷传参**：

| 运维脚本 | 快捷参数示例 | 功能说明 |
| :--- | :--- | :--- |
| **`./4-start.sh`** | `./4-start.sh`<br>`./4-start.sh java`<br>`./4-start.sh 0` | 启动服务容器。<br>直接运行提供菜单，支持仅拉起单个容器（如 Java/Nginx/DB）或全部服务 |
| **`./5-stop.sh`** | `./5-stop.sh`<br>`./5-stop.sh 1`<br>`./5-stop.sh all` | 停止服务容器。<br>支持单独安全停止指定组件，或一键销毁全量容器（保留持久化数据卷） |
| **`./6-restart.sh`** | `./6-restart.sh`<br>`./6-restart.sh java`<br>`./6-restart.sh 2` | 重启服务容器。<br>支持针对单组件重新构建重启（如更新 Jar 包或 Nginx 配置），或全局热重启 |
| **`./ssl/ssl.sh`** | `./ssl/ssl.sh`<br>`./ssl/ssl.sh on`<br>`./ssl/ssl.sh off` | 一键开启/关闭 SSL/HTTPS。<br>自动检测架构签发证书、配置 Nginx 路由，并自动重启 Nginx 网关生效 |
| **`./uninstall_docker.sh`** | `sudo ./uninstall_docker.sh` | 完全卸载清理。<br>安全确认后彻底卸载 Docker、Docker Compose、服务单元及相关数据目录 |

### 交互菜单选项映射表：
```text
  0) 全部服务容器 (All Services) - [默认]
  1) Java 业务后端   (app-java)
  2) Nginx 网关      (app-nginx)
  3) 数据库          (当前选定数据库，自动识别 openGauss 或 MySQL)
  4) Redis 缓存      (app-redis)
  5) EMQX 消息队列   (app-emqx)
  6) SeaweedFS 存储  (app-seaweedfs)
  7) go2rtc 视频流   (app-go2rtc)
```

---

## 五、 SSL / HTTPS 安全证书管理 (一键开启与关闭)

平台内置了开箱即用的离线 SSL 证书套件（位于 `ssl/` 目录），已预置适配主流架构（`x86_64` 与 `aarch64` 麒麟/飞腾）的 `mkcert` 二进制文件，支持随时一键**开启**或**关闭** HTTPS 访问模式，无需繁琐的手动配置。

### 1. 交互式菜单运行 (推荐)
直接运行脚本，按提示选择对应数字：
```bash
./ssl/ssl.sh
```
- **选项 1) 开启 SSL**：
  - 自动识别系统硬件架构并调用匹配的二进制签发工具；
  - 自动探测局域网物理 IP（自动过滤虚拟网段）并规划包含 `localhost`、`127.0.0.1` 及主网卡 IP；
  - 签发 Nginx 所需的服务端证书 `server.crt` 和私钥 `server.key`；
  - 自动将 HTTPS 模版应用为 Nginx 默认配置，并在 80 端口与 443 端口部署根证书直链下载路由 `/rootca.crt`；
  - 将根证书 `rootca.crt` 与服务端证书同步至容器挂载目录；
  - **最后自动重启 Nginx 网关容器使配置生效**。
- **选项 2) 关闭 SSL**：
  - 还原 Nginx 为标准 HTTP 基础配置；
  - 清空证书目录；
  - **最后自动重启 Nginx 网关容器恢复 HTTP 运行**。

### 2. 命令行免交互快捷调用
```bash
# 一键开启 SSL (使用检测到的本机物理 IP 与 localhost 签发并重启生效)
./ssl/ssl.sh on
# 或
./ssl/ssl.sh 1

# 开启 SSL 并追加指定局域网自定义域名与外部 IP
./ssl/ssl.sh on 192.168.1.100 robot.local admin.robot.lan

# 一键关闭 SSL (还原为 HTTP 基础配置、清空证书并重启生效)
./ssl/ssl.sh off
# 或
./ssl/ssl.sh 2
```

### 3. 客户端信任证书（点亮小绿锁）
生成的服务端证书由内置的专用 Root CA 签发。为了让访问平台的客户端电脑（Windows / Mac）或移动设备浏览器显示安全小绿锁、消除“不安全连接”警告：
1. **下载根证书**：
   - **推荐方式**：客户端浏览器直接访问 `http://<服务器IP>/rootca.crt`（HTTP 直链免除证书告警拦截，直接弹出下载）；
   - **备用方式**：访问 `https://<服务器IP>/rootca.crt`（若提示连接非私密，点击“高级” -> “继续前往”即可触发下载）。
2. **导入系统受信任库**：
   - **Windows**：双击下载的 `rootca.crt` -> 点击“安装证书” -> 选择“本地计算机”或“当前用户” -> 选择“将所有的证书都放入下列存储” -> 浏览选择 **“受信任的根证书颁发机构”** -> 一路完成导入。
   - **macOS**：双击 `rootca.crt` 导入“钥匙串访问” -> 找到该证书 -> 双击打开展开“信任” -> 设置为 **“始终信任”**。
3. **完全重启浏览器**，再次访问 `https://<服务器IP>` 即可无警告安全访问。

> [!NOTE]
> 根证书文件（`rootCA.pem` / `rootCA-key.pem`）在反复开启、关闭或重新签发证书时均会保持稳定持久化，**客户端只需导入一次即可永久信任**，无需因服务器重新生成证书而反复安装。

---

## 六、 核心设计亮点与关键配置

### 1. 挂载目录智能初始化 (`2-chmod.sh`)
自动基于 `app-init/` 模板目录进行差异比对。初次部署时将 `jars/`、`nginx/` 等模板完整同步至宿主机 `${DATA_DIR}`，后续执行采用增量补充模式，绝不覆盖用户已有业务数据与已修改配置。

### 2. 多数据库引擎无缝平替（openGauss / MySQL 双适配）
- 支持国产化合规的 openGauss 6.0 与主流开源 MySQL 8.0，通过 Docker Compose `--profile` 动态编排，不产生任何多余资源占用；
- 配套提供双数据库初始化 SQL（`init-opengauss.sql` 与 `init-mysql.sql`），已做好方言转换、字段类型映射及外键关键字转义；
- 脚本自适应记录 `DB_TYPE`，保证拉起、启停与重启脚本配置严格协同一致。

### 3. SeaweedFS 默认目录自动创建
通过在 `docker-compose.yml` 的启动命令中加入自动化守护指令，容器启动后后台自动探测 Filer 就绪状态，并自动在文件系统根目录及 S3 存储桶下创建 **`robot_surveillance/`** 目录，开箱即用。

### 4. openGauss 国产化适配调优
- **4GB 共享内存**：配置 `shm_size: 4gb`，解决 openGauss 底层分配 3.3GB 共享内存引发的段错误崩溃；
- **特权模式与句柄优化**：配置 `privileged: true` 及 `nofile: 1000000`，满足国产 Linux 内核下 openGauss 对 cgroup 控制与高并发连接的需求。

### 5. 离线环境多路径自适应加载
`3-deploy.sh` 脚本内置了智能判定：优先匹配 Docker 现有镜像；未加载时，会自动检索 `docker-image/`、`docker-images/`、`${SCRIPT_DIR}/docker-image/` 等路径下带架构标识（如 `-arm64.tar` 或 `-amd64.tar`）的归档包完成离线装载。

---

## 七、 常见问题与排障锦囊 (FAQ)

### Q1: 为什么在宿主机上普通用户无法访问 `app/opengauss/data` 目录？
- **排查原因**：这是 openGauss / PostgreSQL 底层内核的安全限制。容器启动时会自动将数据目录赋予容器内的专属账户 `omm`（UID 70），并将文件权限严格设置为 `drwx------ (0700)`。数据库引擎在启动时会强校验该权限，**若强行将目录改为 755 或 777，数据库将因安全违规而报 `FATAL: data directory has group or world access` 崩溃退出**。
- **推荐操作**：
  1. **查看与管理表数据**：无需直接接触底层物理块文件，使用数据库客户端（DBeaver、Navicat 等）直接连接宿主机 `5432` 端口即可；
  2. **终端交互查询**：直接运行 `docker exec -it app-opengauss su - omm -c "gsql -d postgres -U gaussdb"`；
  3. **免 sudo 清空数据重置**：`docker run --rm -v ${DATA_DIR}/opengauss:/clean alpine rm -rf /clean/data`。

### Q2: 启动 Java 后端报 `InvalidConfigDataPropertyException: Property 'spring.profiles.active' ... is invalid in a profile specific resource`
- **排查原因**：Spring Boot 2.4+ 规定不允许在以 `application-{profile}.yml` 命名的 Profile 特定配置文件内再声明 `spring.profiles.active`。
- **解决方法**：检查 `application-cususer.yml`，将内部内嵌的 `spring.profiles.active` 行注释掉，统一由 `docker-compose.yml` 的环境变量 `SPRING_PROFILES_ACTIVE` 传递激活。

### Q3: 启动容器报 `OCI runtime create failed: ... permission denied` 或 `flag provided but not defined: -keep`
- **排查原因**：系统中安装了过旧版本的 `runc`（常见于 `/usr/local/bin/runc` 是旧版，覆盖了系统 `/usr/bin/runc`）。
- **解决方法**：
  ```bash
  which runc && runc --version
  # 若显示为旧版本（如 1.0.0-rc3），移走旧版本并重启 Docker
  mv /usr/local/bin/runc /usr/local/bin/runc.bak
  systemctl restart docker
  ```

### Q4: openGauss 提示 `FATAL: The account has been locked`
- **排查原因**：密码输入错误次数达到上限，账号被安全策略自动锁死。
- **解决方法**：在容器内执行解锁命令：
  ```bash
  docker exec -i app-opengauss su - omm -c "source ~/.bashrc; gsql -d postgres -c \"ALTER USER gaussdb ACCOUNT UNLOCK;\""
  docker exec -i app-opengauss su - omm -c "source ~/.bashrc; gsql -d postgres -c \"ALTER USER gaussdb IDENTIFIED BY 'CHANGE_ME';\""
  ```

### Q5: 报错 `Bind for 0.0.0.0:8080 failed: port is already allocated`
- **排查原因**：两个容器绑定了宿主机同一个端口（如 SeaweedFS 的 Volume 与 Java 后端默认抢占 8080）。
- **解决方法**：检查 `.env` 文件，确保各组件暴露端口互不冲突（本项目已将 SeaweedFS Volume 默认移至 `8085`）。

### Q6: go2rtc 的 WebRTC 画面无法播放，但 MSE 正常
- **排查原因**：Docker 默认桥接网络隔离了 WebRTC 的 UDP 握手数据包，或客户端未获得宿主机真实 Candidate IP。
- **解决方法**：
  1. 在 URL 中指定 Candidate 测试：`http://<IP>:1984/stream.html?src=work&mode=webrtc&candidate=<宿主机IP>`；
  2. 宿主机防火墙放行 UDP 8555：`firewall-cmd --add-port=8555/udp --permanent && firewall-cmd --reload`；
  3. 若源流是 H.265，因 Chrome/Edge 原生 WebRTC 不支持硬解 H.265，请在播放地址加入 `&media=video` 或采用 MSE/WebCodecs 模式播放。
