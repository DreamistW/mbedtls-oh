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

## 安装与接入

从 [GitHub Release](https://github.com/DreamistW/mbedtls-oh/releases/tag/v0.1.0)
下载 HAR 和 SHA-256 校验文件。在宿主模块目录核对哈希后安装。

```sh
ohpm install ./mbedtls-oh-0.1.0.har
```

假设 `CMakeLists.txt` 位于宿主模块的 `src/main/cpp`，`oh_modules` 位于模块根目录。

```cmake
include("${CMAKE_CURRENT_SOURCE_DIR}/../../../oh_modules/mbedtls-oh/include/mbedtls-oh.cmake")
target_link_libraries(your_native_target PRIVATE mbedtls-oh::tls)
```

`mbedtls-oh::tls` 提供公共头文件，并依次链接 `libmbedtls.a`、`libmbedx509.a` 和
`libmbedcrypto.a`。应用使用 socket 时，在宿主模块的 `module.json5` 声明
`ohos.permission.INTERNET`。ArkTS 通过宿主的 NAPI 模块调用原生实现。

## 基本功能示例

### 计算 SHA-256

```c
#include <mbedtls/sha256.h>

int hash_bytes(const unsigned char *data, size_t length, unsigned char digest[32])
{
    return mbedtls_sha256(data, length, digest, 0);
}
```

调用方提供 32 字节输出缓冲区。返回 `0` 表示成功，输入可以包含零字节。

### 验证服务器证书并收发 TLS 数据

在原生工作线程运行。调用前执行 `psa_crypto_init()` 并检查返回值为 `PSA_SUCCESS`，
声明见 `<psa/crypto.h>`。传入服务端 DNS 名称、端口、可信渠道取得的 PEM 根 CA
和应用协议的请求字节。调用方提供非空响应缓冲区，示例返回首块响应的字节数。需要完整响应时，按应用协议的消息边界继续读，
并设置总时限。

```c
#include <mbedtls/ctr_drbg.h>
#include <mbedtls/entropy.h>
#include <mbedtls/net_sockets.h>
#include <mbedtls/ssl.h>
#include <mbedtls/x509_crt.h>
#include <string.h>

int read_tls_reply(const char *host, const char *port, const char *ca_pem,
                   const unsigned char *request, size_t request_length,
                   unsigned char *reply, size_t reply_capacity)
{
    mbedtls_net_context socket;
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context random;
    mbedtls_x509_crt ca;
    mbedtls_ssl_config config;
    mbedtls_ssl_context tls;
    int rc;

    mbedtls_net_init(&socket);
    mbedtls_entropy_init(&entropy);
    mbedtls_ctr_drbg_init(&random);
    mbedtls_x509_crt_init(&ca);
    mbedtls_ssl_config_init(&config);
    mbedtls_ssl_init(&tls);

    rc = mbedtls_ctr_drbg_seed(&random, mbedtls_entropy_func, &entropy, NULL, 0);
    if (rc != 0) { goto cleanup; }
    rc = mbedtls_x509_crt_parse(&ca, (const unsigned char *) ca_pem, strlen(ca_pem) + 1);
    if (rc != 0) {
        // PEM 中有证书解析失败时也拒绝连接。
        if (rc > 0) { rc = MBEDTLS_ERR_X509_INVALID_FORMAT; }
        goto cleanup;
    }
    rc = mbedtls_ssl_config_defaults(&config, MBEDTLS_SSL_IS_CLIENT,
                                     MBEDTLS_SSL_TRANSPORT_STREAM, MBEDTLS_SSL_PRESET_DEFAULT);
    if (rc != 0) { goto cleanup; }
    mbedtls_ssl_conf_authmode(&config, MBEDTLS_SSL_VERIFY_REQUIRED);
    mbedtls_ssl_conf_ca_chain(&config, &ca, NULL);
    mbedtls_ssl_conf_rng(&config, mbedtls_ctr_drbg_random, &random);
    mbedtls_ssl_conf_read_timeout(&config, 10000);
    rc = mbedtls_ssl_setup(&tls, &config);
    if (rc != 0) { goto cleanup; }
    rc = mbedtls_ssl_set_hostname(&tls, host);
    if (rc != 0) { goto cleanup; }
    rc = mbedtls_net_connect(&socket, host, port, MBEDTLS_NET_PROTO_TCP);
    if (rc != 0) { goto cleanup; }
    mbedtls_ssl_set_bio(&tls, &socket, mbedtls_net_send, NULL, mbedtls_net_recv_timeout);

    do {
        rc = mbedtls_ssl_handshake(&tls);
    } while (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE);
    if (rc != 0) { goto cleanup; }

    for (size_t sent = 0; sent < request_length;) {
        rc = mbedtls_ssl_write(&tls, request + sent, request_length - sent);
        if (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE) { continue; }
        if (rc <= 0) {
            if (rc == 0) { rc = MBEDTLS_ERR_NET_SEND_FAILED; }
            goto cleanup;
        }
        sent += (size_t) rc;
    }
    do {
        rc = mbedtls_ssl_read(&tls, reply, reply_capacity);
    } while (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE);
    if (rc > 0) { (void) mbedtls_ssl_close_notify(&tls); }

cleanup:
    mbedtls_ssl_free(&tls);
    mbedtls_ssl_config_free(&config);
    mbedtls_x509_crt_free(&ca);
    mbedtls_ctr_drbg_free(&random);
    mbedtls_entropy_free(&entropy);
    mbedtls_net_free(&socket);
    return rc;
}
```

读取返回 `0` 表示收到数据前连接已结束，负值由调用方按 TLS 错误码处理。
示例使用调用方提供的 CA，宿主需要选择可信的证书来源。读取超时为 10 秒，
TCP 建连和整个请求的截止时间由宿主管理。
完整接口见 [Mbed TLS 3.6.7 API 文档](https://mbed-tls.readthedocs.io/projects/api/en/v3.6.7/api/file/ssl_8h/)。

## GitHub Release

推送 `main` 运行构建并上传 Actions artifact。推送与包版本一致的稳定标签
（例如 `v0.1.0`）发布版本化 HAR 与 SHA-256 校验文件。CI 使用按摘要固定的 API 26 镜像。

## 许可

构建和打包代码使用 Apache-2.0。Mbed TLS 按 Apache-2.0 分发，完整许可随包提供。
