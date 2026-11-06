# 导出 HAR 内的 TLS、X.509 和密码学静态库，供消费者最终链接。
if(TARGET mbedtls-oh::tls)
  return()
endif()
if(NOT OHOS_ARCH STREQUAL "arm64-v8a")
  message(FATAL_ERROR "mbedtls-oh requires arm64-v8a")
endif()

foreach(_component mbedcrypto mbedx509 mbedtls)
  set(_archive "${CMAKE_CURRENT_LIST_DIR}/../libs/${OHOS_ARCH}/lib${_component}.a")
  if(NOT EXISTS "${_archive}")
    message(FATAL_ERROR "Missing mbedtls-oh archive for ${_component}")
  endif()
  add_library(mbedtls-oh::${_component} STATIC IMPORTED GLOBAL)
  set_target_properties(mbedtls-oh::${_component} PROPERTIES
    IMPORTED_LOCATION "${_archive}"
    INTERFACE_INCLUDE_DIRECTORIES "${CMAKE_CURRENT_LIST_DIR}")
endforeach()
set_property(TARGET mbedtls-oh::mbedx509 PROPERTY INTERFACE_LINK_LIBRARIES mbedtls-oh::mbedcrypto)
set_property(TARGET mbedtls-oh::mbedtls PROPERTY INTERFACE_LINK_LIBRARIES mbedtls-oh::mbedx509)
add_library(mbedtls-oh::tls ALIAS mbedtls-oh::mbedtls)
unset(_archive)
unset(_component)
