"""One profile per MT5 account: its own folder with settings, state, log and Telegram login.

    profiles/<name>/config.json       groups, risk, allow_live, terminal path, login
    profiles/<name>/state_*.json      start balance, loss stop, signal -> tickets
    profiles/<name>/copier.log
    profiles/<name>/telegram.session  this profile's own Telegram login

    python -m signal_copier.profiles new <name>   -> folder, desktop shortcuts, Notepad
    python -m signal_copier.profiles autostart <name>   -> starts with Windows, restarts if it stops
    python -m signal_copier.profiles list

Each profile runs in its own window against its own MT5 installation: the
MetaTrader5 package talks to exactly one terminal per process.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PROFILES = HERE / "profiles"
TEMPLATE = HERE / "profile_template.json"
NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


class ProfileError(RuntimeError):
    pass


def names() -> list[str]:
    if not PROFILES.exists():
        return []
    return sorted(p.name for p in PROFILES.iterdir() if (p / "config.json").exists())


def folder(name: str) -> Path:
    if not NAME.match(name):
        raise ProfileError(f"{name!r}: only lowercase letters, digits, _ and -")
    return PROFILES / name


def pick(name: str | None) -> str:
    """The profile to run: the one named, or the only one there is."""
    available = names()
    if name:
        if name not in available:
            raise ProfileError(f"no profile {name!r}; there are: {', '.join(available) or 'none'}")
        return name
    if len(available) == 1:
        return available[0]
    if not available:
        raise ProfileError("no profile yet -- run neues_profil.bat first")
    raise ProfileError(f"several profiles, name one: {', '.join(available)}")


def load(name: str) -> dict:
    return json.loads((folder(name) / "config.json").read_text(encoding="utf-8"))


def create(name: str) -> Path:
    target = folder(name)
    if target.exists():
        raise ProfileError(f"profile {name!r} exists already: {target}")
    target.mkdir(parents=True)
    shutil.copyfile(TEMPLATE, target / "config.json")
    return target / "config.json"


def desktop_shortcuts(name: str) -> None:
    """'Copier <name>' starts it, 'Copier <name> Einstellungen' opens its settings."""
    start = HERE / "start.bat"
    config = folder(name) / "config.json"
    ps = f"""
$d = [Environment]::GetFolderPath('Desktop'); $w = New-Object -ComObject WScript.Shell
$s = $w.CreateShortcut("$d\\Copier {name}.lnk"); $s.TargetPath = '{start}'; $s.Arguments = '{name}'
$s.WorkingDirectory = '{HERE.parent}'; $s.Save()
$c = $w.CreateShortcut("$d\\Copier {name} Einstellungen.lnk"); $c.TargetPath = 'notepad.exe'
$c.Arguments = '"{config}"'; $c.Save()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def autostart_shortcut(name: str) -> Path:
    """A shortcut in Windows' Startup folder: the profile starts at logon, without a window
    (tools\\run_hidden.vbs; tools\\stop_helpers.bat copiers stops it), and autostart.bat restarts it if it
    ever stops. Without it, a reboot (Windows updates do that at night) silently ends copying until someone notices."""
    folder(name)  # validates the name
    if name not in names():
        raise ProfileError(f"no profile {name!r}")
    bat = HERE / "autostart.bat"
    hidden = HERE.parent / "tools" / "run_hidden.vbs"
    ps = f"""
$s = [Environment]::GetFolderPath('Startup'); $w = New-Object -ComObject WScript.Shell
$l = $w.CreateShortcut("$s\\Copier {name}.lnk"); $l.TargetPath = 'C:\\Windows\\System32\\wscript.exe'
$l.Arguments = '"{hidden}" "{bat}" {name}'
$l.WorkingDirectory = '{HERE.parent}'; $l.Save(); Write-Output "$s\\Copier {name}.lnk"
"""
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True, text=True)
    return Path(out.stdout.strip())


def main(argv: list[str]) -> None:
    if len(argv) == 2 and argv[0] == "autostart":
        try:
            print(f"Starts at logon: {autostart_shortcut(argv[1])}")
        except ProfileError as e:
            raise SystemExit(str(e))
        return
    if argv[:1] == ["list"]:
        print("\n".join(names()) or "no profiles yet")
        return
    if len(argv) == 2 and argv[0] == "new":
        try:
            config = create(argv[1])
        except ProfileError as e:
            raise SystemExit(str(e))
        desktop_shortcuts(argv[1])
        print(f"Created {config}\nDesktop: 'Copier {argv[1]}' and 'Copier {argv[1]} Einstellungen'.")
        subprocess.Popen(["notepad.exe", str(config)])
        return
    raise SystemExit("usage: python -m signal_copier.profiles new <name> | autostart <name> | list")


if __name__ == "__main__":
    main(sys.argv[1:])
