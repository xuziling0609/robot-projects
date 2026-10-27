# Robot Projects

本仓库汇总了机器人项目中的三组源码：

- `arm_project`：机械臂控制、视觉检测、标定和部署相关代码。
- `robot_project`：机器人主控、插件、传感器接入、模拟器及测试代码。
- `robot-deploy`：Docker 部署、数据库初始化、配置和运维脚本。

## 说明

此版本用于 GitHub 源码托管。以下内容未提交：

- 含真实账号、密码或令牌的本地配置；部署配置请参考 `.env.example`。
- Docker 镜像包、离线安装包、模型、轮子包、JAR 和大型运行程序等二进制制品。
- 原项目内部 Git 仓库的历史记录；本仓库使用独立的初始提交。

恢复运行环境时，请根据各项目 README 安装依赖，并复制 `robot-deploy/.env.example` 为 `.env` 后填写本地值。
