import shlex
import subprocess

from rich.prompt import Confirm

from hackingtool.core import HackingTool, HackingToolsCollection, console
from hackingtool.constants import PRIV_CMD, USER_CONFIG_DIR, REPO_WEB_URL


def _run_system_update(command: str, os_info) -> bool:
    """Execute a hard-coded package-manager update without a shell."""
    steps = [
        shlex.split(step.strip())
        for step in command.split("&&")
        if step.strip()
    ]
    if not steps or any(not step for step in steps):
        return False

    privilege = (
        [PRIV_CMD]
        if os_info.system == "linux" and not os_info.is_root
        else []
    )
    for step in steps:
        try:
            result = subprocess.run([*privilege, *step], check=False)
        except OSError:
            return False
        if result.returncode != 0:
            return False
    return True


class UpdateTool(HackingTool):
    TITLE = "Update Tool or System"
    DESCRIPTION = "Update system packages or pull the latest hackingtool code"

    def __init__(self):
        super().__init__([
            ("Update System", self.update_sys),
            ("Update Hackingtool", self.update_ht),
        ], installable=False, runnable=False)

    def update_sys(self):
        from hackingtool.os_detect import CURRENT_OS, PACKAGE_UPDATE_CMDS
        mgr = CURRENT_OS.pkg_manager
        cmd = PACKAGE_UPDATE_CMDS.get(mgr)
        if not cmd:
            console.print("[warning]Unknown package manager — update manually.[/warning]")
            return
        if _run_system_update(cmd, CURRENT_OS):
            console.print(f"[success]✔ Updated packages with {mgr}.[/success]")
        else:
            console.print(f"[error]✘ {mgr} update failed.[/error]")

    def update_ht(self):
        # hackingtool ships as a standard package (pipx/pip/.deb/docker). It can't
        # reliably self-update its own installed package from inside, so show the
        # right command for each channel instead of a broken git-pull.
        console.print("[bold cyan]Update hackingtool with the command for how you installed it:[/bold cyan]")
        console.print("  pipx     [success]pipx upgrade hackingtool[/success]")
        console.print("  pip      [success]pip install --upgrade hackingtool[/success]")
        console.print("  .deb     download the latest .deb, then [success]sudo apt install ./<file>.deb[/success]")
        console.print("  docker   [success]docker pull ghcr.io/z4nzu/hackingtool:latest[/success]")
        console.print(f"[dim]Latest release: {REPO_WEB_URL}/releases/latest[/dim]")


class UninstallTool(HackingTool):
    TITLE = "Uninstall HackingTool"
    DESCRIPTION = "Remove hackingtool from system"

    def __init__(self):
        super().__init__([
            ("Uninstall", self.uninstall),
        ], installable=False, runnable=False)

    def uninstall(self):
        import shutil
        # Remove the package itself with the channel's own command (we can't
        # uninstall our own pipx/pip/apt package from inside it). We can clean up
        # the one thing we own regardless of install method: the ~/.hackingtool data.
        console.print("[warning]Remove the hackingtool package with the command for how you installed it:[/warning]")
        console.print("  pipx     [success]pipx uninstall hackingtool[/success]")
        console.print("  pip      [success]pip uninstall hackingtool[/success]")
        console.print("  .deb     [success]sudo apt remove python3-hackingtool[/success]")
        console.print("  docker   [success]docker rmi ghcr.io/z4nzu/hackingtool:latest[/success]")

        if USER_CONFIG_DIR.exists() and Confirm.ask(
                f"Remove your data + installed tools at {USER_CONFIG_DIR} now?", default=False):
            shutil.rmtree(str(USER_CONFIG_DIR), ignore_errors=True)
            console.print(f"[success]✔ Removed {USER_CONFIG_DIR}[/success]")


class ToolManager(HackingToolsCollection):
    TITLE = "Update or Uninstall | Hackingtool"
    TOOLS = [
        UpdateTool(),
        UninstallTool(),
    ]


if __name__ == "__main__":
    manager = ToolManager()
    manager.show_options()
