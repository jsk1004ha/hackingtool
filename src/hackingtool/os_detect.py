import platform
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OSInfo:
    system: str                    # "linux", "macos", "windows", "unknown"
    distro_id: str        = ""     # "kali", "ubuntu", "arch", "fedora", etc.
    distro_like: str      = ""     # "debian", "rhel", etc. (from ID_LIKE)
    distro_version: str   = ""     # "2024.1", "22.04", etc.
    pkg_manager: str      = ""     # "apt-get", "pacman", "dnf", "brew", etc.
    is_root: bool         = False
    home_dir: Path        = field(default_factory=Path.home)
    is_wsl: bool          = False  # Windows Subsystem for Linux
    arch: str             = ""     # "x86_64", "aarch64", "arm64"


def detect() -> OSInfo:
    """
    Fully detect the current OS, distro, and available package manager.
    Never asks the user — entirely automatic.
    """
    import os

    system_raw = platform.system()
    system = system_raw.lower()
    if system == "darwin":
        system = "macos"

    info = OSInfo(
        system  = system,
        is_root = (os.geteuid() == 0) if hasattr(os, "geteuid") else False,
        home_dir = Path.home(),
        arch    = platform.machine(),
    )

    # ── Linux-specific ─────────────────────────────────────────────────────────
    if system == "linux":
        # Detect WSL
        try:
            info.is_wsl = "microsoft" in Path("/proc/version").read_text().lower()
        except (FileNotFoundError, PermissionError):
            pass

        # Read /etc/os-release (standard on all modern distros)
        os_release: dict[str, str] = {}
        for path in ("/etc/os-release", "/usr/lib/os-release"):
            try:
                for line in Path(path).read_text().splitlines():
                    k, _, v = line.partition("=")
                    os_release[k.strip()] = v.strip().strip('"')
                break
            except FileNotFoundError:
                continue

        info.distro_id      = os_release.get("ID", "").lower()
        info.distro_like    = os_release.get("ID_LIKE", "").lower()
        info.distro_version = os_release.get("VERSION_ID", "")

    # ── Package manager detection (in priority order) ──────────────────────────
    for mgr in ("apt-get", "pacman", "dnf", "zypper", "apk", "brew", "pkg"):
        if shutil.which(mgr):
            info.pkg_manager = mgr
            break

    return info


# Module-level singleton — computed once on import
CURRENT_OS: OSInfo = detect()


# ── Per-OS package manager commands ────────────────────────────────────────────
# Store install commands as argv prefixes so execution never needs a shell.
# PACKAGE_INSTALL_CMDS stays available for display/backward compatibility.
_PACKAGE_INSTALL_PREFIXES: dict[str, tuple[str, ...]] = {
    "apt-get": ("apt-get", "install", "-y"),
    "pacman":  ("pacman", "-S", "--noconfirm"),
    "dnf":     ("dnf", "install", "-y"),
    "zypper":  ("zypper", "install", "-y"),
    "apk":     ("apk", "add"),
    "brew":    ("brew", "install"),
    "pkg":     ("pkg", "install", "-y"),
}

PACKAGE_INSTALL_CMDS: dict[str, str] = {
    manager: f"{shlex.join(prefix)} {{packages}}"
    for manager, prefix in _PACKAGE_INSTALL_PREFIXES.items()
}

PACKAGE_UPDATE_CMDS: dict[str, str] = {
    "apt-get": "apt-get update -qq && apt-get upgrade -y",
    "pacman":  "pacman -Syu --noconfirm",
    "dnf":     "dnf upgrade -y",
    "zypper":  "zypper update -y",
    "apk":     "apk update && apk upgrade",
    "brew":    "brew update && brew upgrade",
    "pkg":     "pkg update && pkg upgrade -y",
}

# Core system packages needed per package manager
REQUIRED_PACKAGES: dict[str, list[str]] = {
    "apt-get": ["git", "python3-pip", "python3-venv", "curl", "wget",
                "ruby", "ruby-dev", "golang-go", "php", "default-jre-headless"],
    "pacman":  ["git", "python-pip", "curl", "wget",
                "ruby", "go", "php", "jre-openjdk-headless"],
    "dnf":     ["git", "python3-pip", "curl", "wget",
                "ruby", "golang", "php", "java-17-openjdk-headless"],
    "zypper":  ["git", "python3-pip", "curl", "wget", "ruby", "go", "php"],
    "brew":    ["git", "python3", "curl", "wget", "ruby", "go", "php"],
    "pkg":     ["git", "python3", "py39-pip", "curl", "wget", "ruby", "go", "php83"],
}


def _package_install_argv(
    packages: list[str],
    os_info: OSInfo,
) -> list[str] | None:
    """Build a package-manager argv without invoking a shell."""
    prefix = _PACKAGE_INSTALL_PREFIXES.get(os_info.pkg_manager)
    if prefix is None:
        return None

    normalized: list[str] = []
    for package in packages:
        if not isinstance(package, str):
            raise TypeError("package names must be strings")
        package = package.strip()
        if not package or "\x00" in package or any(char.isspace() for char in package):
            raise ValueError(f"invalid package name: {package!r}")
        if package.startswith("-"):
            raise ValueError(f"package name cannot be an option: {package!r}")
        normalized.append(package)

    command = [*prefix, *normalized]
    if os_info.system == "linux" and not os_info.is_root:
        from hackingtool.constants import PRIV_CMD
        command.insert(0, PRIV_CMD)
    return command


def install_packages(packages: list[str], os_info: OSInfo | None = None) -> bool:
    """Install system packages using the detected package manager.

    Package names are passed as literal argv entries and never interpreted by a
    shell.
    """
    if os_info is None:
        os_info = CURRENT_OS

    try:
        command = _package_install_argv(packages, os_info)
    except (TypeError, ValueError) as exc:
        print(f"[warning] Refusing invalid package request: {exc}")
        return False

    if command is None:
        print(f"[warning] Unknown package manager. Install manually: {packages}")
        return False
    if not packages:
        return True

    try:
        result = subprocess.run(command, check=False)
    except OSError as exc:
        print(f"[warning] Could not execute {os_info.pkg_manager}: {exc}")
        return False
    return result.returncode == 0
