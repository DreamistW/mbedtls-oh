"""构建、检查和打包锁定的 HarmonyOS Mbed TLS 静态库。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

from har import build_har, verify_har

ROOT = Path(__file__).resolve().parents[1]
ABI = "arm64-v8a"
LIBS = ("libmbedtls.a", "libmbedx509.a", "libmbedcrypto.a")


def sdk_tool(path: Path) -> Path:
    """根据主机平台选择工具文件名，SDK 根路径由调用者提供。"""
    return path.with_suffix(".exe") if os.name == "nt" else path


def source_archive(path: Path, lock: dict) -> Path:
    """校验官方源码归档，下载成功后再写入缓存。"""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=path.parent) as temporary:
            pending = Path(temporary) / path.name
            with urllib.request.urlopen(lock["url"], timeout=120) as response, pending.open("wb") as output:
                shutil.copyfileobj(response, output)
            with pending.open("rb") as downloaded:
                if hashlib.file_digest(downloaded, "sha256").hexdigest() != lock["sha256"]:
                    raise ValueError("Mbed TLS download hash differs from dependency lock")
            pending.replace(path)
    with path.open("rb") as cached:
        if hashlib.file_digest(cached, "sha256").hexdigest() != lock["sha256"]:
            raise ValueError("Mbed TLS source archive hash differs from dependency lock")
    return path


def build_native(sdk: Path, archive: Path, version: str, workspace: Path) -> Path:
    """从已校验源码创建独立构建目录，生成三份 PIC 静态库。"""
    with tarfile.open(archive, "r:bz2") as source:
        source.extractall(workspace, filter="data")
    native = sdk / "sdk/default/openharmony/native"
    cmake = sdk_tool(native / "build-tools/cmake/bin/cmake")
    ninja = sdk_tool(native / "build-tools/cmake/bin/ninja")
    toolchain = sdk / "sdk/default/hms/native/build/cmake/hmos.toolchain.cmake"
    src = workspace / f"mbedtls-{version}"
    build = workspace / "native-build"
    install = workspace / "install"
    mapping = f"-ffile-prefix-map={workspace.as_posix()}=."
    subprocess.run([
        cmake, "-S", src, "-B", build, "-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={ninja}",
        f"-DCMAKE_TOOLCHAIN_FILE={toolchain}", f"-DOHOS_SDK_NATIVE={native}",
        f"-DOHOS_ARCH={ABI}", "-DOHOS_PLATFORM_LEVEL=26", "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
        f"-DCMAKE_C_FLAGS={mapping} -Wno-unused-command-line-argument",
        "-DENABLE_PROGRAMS=OFF", "-DENABLE_TESTING=OFF", "-DUSE_SHARED_MBEDTLS_LIBRARY=OFF",
        "-DUSE_STATIC_MBEDTLS_LIBRARY=ON", "-DCMAKE_INSTALL_LIBDIR=lib",
        f"-DCMAKE_INSTALL_PREFIX={install}",
    ], check=True)
    subprocess.run([cmake, "--build", build, "--parallel"], check=True)
    subprocess.run([cmake, "--install", build], check=True)
    shutil.copyfile(src / "LICENSE", install / "MbedTLS-LICENSE.txt")
    return install


def prepare(install: Path, lock: dict) -> dict:
    """装配头文件、静态库、许可和逐文件哈希。"""
    library = ROOT / "library"
    included = {}
    for folder in ("mbedtls", "psa"):
        target = library / "include" / folder
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(install / "include" / folder, target)
        included.update({f"include/{folder}/{p.name}": p for p in target.glob("*.h")})
    lib = library / "libs" / ABI
    lib.mkdir(parents=True, exist_ok=True)
    for name in LIBS:
        target = lib / name
        shutil.copyfile(install / "lib" / name, target)
        included[f"libs/{ABI}/{name}"] = target
    licenses = library / "licenses"
    licenses.mkdir(exist_ok=True)
    shutil.copyfile(install / "MbedTLS-LICENSE.txt", licenses / "MbedTLS-LICENSE.txt")
    version = json.loads((library / "oh-package.json5").read_text(encoding="utf-8"))["version"]
    manifest = {
        "name": "mbedtls-oh", "version": version, "upstream": lock,
        "platform": {"minApi": 23, "targetApi": 26, "abi": ABI, "deviceType": "2in1"},
        "files": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sorted(included.items())},
    }
    (library / "include/mbedtls-oh-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "build/downloads/mbedtls-3.6.7.tar.bz2")
    args = parser.parse_args()
    sdk = Path(os.environ["DEVECO_CLI_CLT_PATH"]).resolve(strict=True)
    lock = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
    archive = source_archive(args.archive.resolve(), lock["archive"])
    builds = ROOT / "build"
    builds.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mbedtls-", dir=builds) as temporary:
        manifest = prepare(build_native(sdk, archive, lock["version"], Path(temporary)), lock)
    package = build_har(ROOT, sdk, "mbedtls_oh", "mbedtls-oh", manifest["version"])
    verify_har(package, "mbedtls-oh", manifest["version"], manifest["files"], "include/mbedtls-oh-manifest.json")


if __name__ == "__main__":
    main()
