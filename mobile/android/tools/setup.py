"""Install pinned Android build tools and native source. No model downloads."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SDK = Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk"
TOOLS = ROOT / ".tools"
LLAMA_REVISION = "5aeac37a35b44fde4bdffaec9159f2fcb253b622"
GRADLE = "8.9"


def fetch(url, destination, checksum=None, algorithm="sha256"):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and checksum:
        if hashlib.new(algorithm, destination.read_bytes()).hexdigest() == checksum:
            return
    print("Downloading", url, flush=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(url, timeout=90) as source, temporary.open("wb") as target:
        shutil.copyfileobj(source, target, 1024 * 1024)
    if checksum and hashlib.new(algorithm, temporary.read_bytes()).hexdigest() != checksum:
        raise RuntimeError("Checksum mismatch: " + destination.name)
    temporary.replace(destination)


def setup_sdk():
    android_cli = SDK / "cmdline-tools" / "latest" / "bin" / "android.exe"
    manager = SDK / "cmdline-tools" / "latest" / "bin" / "sdkmanager.bat"
    if not android_cli.exists() and not manager.exists():
        archive = TOOLS / "commandlinetools.zip"
        fetch("https://dl.google.com/android/repository/commandlinetools-win-16111833_latest.zip",
              archive, "57d04f2d75eb8e8fffc5000a987e5de4b5a63e9d", "sha1")
        stage = TOOLS / "sdk-unpack"
        with zipfile.ZipFile(archive) as package:
            package.extractall(stage)
        (SDK / "cmdline-tools" / "latest").parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(stage / "cmdline-tools"), str(SDK / "cmdline-tools" / "latest"))
    print("Installing Android SDK 35, platform tools, NDK 27 and CMake 3.22.1", flush=True)
    if android_cli.exists():
        subprocess.run([str(android_cli), "sdk", "install",
                        "platforms/android-35", "build-tools/35.0.0",
                        "ndk/27.2.12479018", "cmake/3.22.1", "platform-tools"], check=True)
    else:
        subprocess.run([str(manager), "--sdk_root=" + str(SDK), "--licenses"],
                       input="y\n" * 100, text=True, check=True)
        subprocess.run([str(manager), "--sdk_root=" + str(SDK), "platform-tools", "platforms;android-35",
                        "build-tools;35.0.0", "ndk;27.2.12479018", "cmake;3.22.1"],
                       input="y\n" * 100, text=True, check=True)
    (ROOT / "local.properties").write_text("sdk.dir=" + SDK.as_posix() + "\n", encoding="utf-8")
    print("SDK_READY", SDK, flush=True)


def setup_gradle():
    base = "https://raw.githubusercontent.com/gradle/gradle/v8.9.0/"
    for relative in ("gradlew", "gradlew.bat", "gradle/wrapper/gradle-wrapper.jar"):
        dest = ROOT / relative
        if not dest.exists():
            fetch(base + relative, dest)
    local_zip = TOOLS / "gradle-8.9-bin.zip"
    if not local_zip.exists():
        fetch("https://github.com/gradle/gradle-distributions/releases/download/v8.9.0/gradle-8.9-bin.zip",
              local_zip, "d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab")
    zip_url = "file:///" + local_zip.as_posix()
    (ROOT / "gradle/wrapper/gradle-wrapper.properties").write_text(
        "distributionBase=GRADLE_USER_HOME\ndistributionPath=wrapper/dists\n"
        f"distributionUrl={zip_url}\n"
        "distributionSha256Sum=d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab\nnetworkTimeout=90000\n"
        "validateDistributionUrl=true\nzipStoreBase=GRADLE_USER_HOME\nzipStorePath=wrapper/dists\n",
        encoding="utf-8")
    subprocess.run([str(ROOT / "gradlew.bat"), "--version"], cwd=ROOT, check=True)
    print("GRADLE_READY", flush=True)


def setup_llama():
    target = ROOT / "third_party" / "llama.cpp"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not (target / ".git").exists():
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/ggml-org/llama.cpp.git", str(target)], check=True)
    revision = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
    if revision != LLAMA_REVISION:
        subprocess.run(["git", "-C", str(target), "fetch", "--depth", "1", "origin", LLAMA_REVISION], check=True)
        subprocess.run(["git", "-C", str(target), "checkout", "--detach", LLAMA_REVISION], check=True)
    print("LLAMA_READY", LLAMA_REVISION, flush=True)


if __name__ == "__main__":
    TOOLS.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(task) for task in (setup_sdk, setup_gradle, setup_llama)]
        for job in jobs:
            job.result()
    print("Setup complete. Run .\\gradlew.bat :app:assembleDebug :app:testDebugUnitTest", flush=True)
