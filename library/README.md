# mbedtls-oh HAR

本包提供 Mbed TLS 3.6.7 的公共 C 头文件和三个静态库。面向 HarmonyOS
最低 API 23、目标 API 26 的 `arm64-v8a` `2in1`。

在消费模块执行 `ohpm install ./mbedtls-oh-0.1.1.har`。将
`MBEDTLS_OH_PACKAGE` 指向实际安装的包目录，引入
`include/mbedtls-oh.cmake` 并链接 `mbedtls-oh::tls`。目标会按顺序传递
`libmbedtls.a`、`libmbedx509.a` 和 `libmbedcrypto.a`。

TLS 策略、证书信任来源和主机名校验由消费者配置。版本和文件哈希见
`include/mbedtls-oh-manifest.json`。Mbed TLS 许可随包提供。
