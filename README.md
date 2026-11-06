# mbedtls-oh

HarmonyOS 原生静态库 HAR。首版基于 Mbed TLS 3.6.7，支持 HarmonyOS
最低 API 23、目标 API 26、`arm64-v8a`、`2in1`。

## 工程内容

- `dependencies.lock.json` 锁定官方源码归档、SHA-256 和上游许可。
- `library/` 包含 HAR 模块与 CMake 导入目标。
- `scripts/` 提供原生构建、HAR 打包与发布审计。

## 构建 HAR

配置 API 26 Command Line Tools 环境变量 `DEVECO_CLI_CLT_PATH`，安装 Python 3.11+
和 JDK 21。从仓库根目录运行以下命令。Windows 还需要支持 `assembleHar` 的 `devecocli`。

```sh
python scripts/build.py
```

构建从锁定的官方源码归档生成三份 PIC 静态库。产物位于 `dist/`，包含
`mbedtls-oh-0.1.0.har` 和 SHA-256 校验文件。可传入 `--archive` 使用已有的同哈希归档。

## 使用

将 Release 中的 HAR 安装到使用 C/C++ 的模块。引入包内的 CMake 配置，并按下例链接。
完整安装和平台说明见 [使用说明](library/README.md)。

```cmake
include("${MBEDTLS_OH_PACKAGE}/include/mbedtls-oh.cmake")
target_link_libraries(your_native_target PRIVATE mbedtls-oh::tls)
```

## GitHub Release

推送 `main` 运行构建并上传 Actions artifact。推送与包版本一致的稳定标签
（例如 `v0.1.0`）发布版本化 HAR 与 SHA-256 校验文件。CI 使用按摘要固定的 API 26 镜像。

## 许可

构建和打包代码使用 Apache-2.0。Mbed TLS 按 Apache-2.0 分发，完整许可随包提供。
