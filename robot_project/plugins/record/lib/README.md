# FFmpeg 多系统与跨架构静态二进制库说明

本目录用于存放免安装、自包含的静态编译 FFmpeg 可执行文件，程序（`FFmpegResolver`）会根据当前运行的操作系统与 CPU 硬件架构自动匹配加载，并自动赋予执行权限（`chmod 755`）。

## 目录组织规范

```text
lib/
├── linux/
│   ├── aarch64/          # Linux 64位 ARM (Jetson Orin/Xavier, RK3588, 飞腾, 树莓派4/5等)
│   │   └── ffmpeg        # Linux aarch64 静态编译无依赖版本
│   └── x86_64/           # Linux 64位 x86 (x86 工控机, Ubuntu 开发机, Docker 容器等)
│       └── ffmpeg        # Linux x86_64 静态编译无依赖版本
├── windows/
│   └── x86_64/           # Windows 64位开发环境 / 仿真测试
│       └── ffmpeg.exe    # Windows x86_64 静态编译版
├── darwin/               # macOS 开发测试环境
│   ├── arm64/            # Apple Silicon (M1/M2/M3/M4 芯片)
│   │   └── ffmpeg
│   └── x86_64/           # Intel Mac
│       └── ffmpeg
└── README.md
```

## 推荐官方静态编译包下载源

- **Linux (aarch64 / x86_64)**: [John Van Sickle FFmpeg Static Builds](https://johnvansickle.com/ffmpeg/)
  - 选择 `ffmpeg-release-arm64-static.tar.xz` (用于 aarch64)
  - 选择 `ffmpeg-release-amd64-static.tar.xz` (用于 x86_64)
- **Windows (x86_64)**: [Gyan.dev FFmpeg Builds](https://www.gyan.dev/ffmpeg/builds/) (选择 `ffmpeg-release-essentials.zip`)
- **macOS (arm64 / x86_64)**: [Evermeet.cx Mac FFmpeg](https://evermeet.cx/ffmpeg/)

## 自动加载优先级

1. `config.yaml` 中配置的 `custom_ffmpeg_path`（若有指定）；
2. 精确匹配当前系统架构目录：`lib/{os}/{arch}/ffmpeg[.exe]`；
3. 扁平匹配：`lib/{os}/ffmpeg[.exe]` 或 `lib/ffmpeg[.exe]`；
4. 宿主机全局环境变量 `PATH` 中的 `ffmpeg`。
