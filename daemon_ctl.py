#!/usr/bin/env python3
"""daemon_ctl.py — Alf 데몬 매니저. dev(Popen) + prod(launchd) 통합 관리."""

import argparse
import json
import os
import plistlib
import signal
import subprocess
import sys
import textwrap

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(PROJECT_ROOT, "run")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
APP_DIR = os.path.join(PROJECT_ROOT, "apps")
PLIST_DIR = os.path.expanduser("~/Library/LaunchAgents")
PLIST_PREFIX = "com.alf"
PYTHON = "/usr/bin/python3"

DAEMONS = {
    "bridge": {
        "script": "src/alf_bridge.py",
        "args": [],
        "desc": "iMessage ↔ inbox/outbox 브릿지",
    },
    "inbox": {
        "script": "src/process_inbox.py",
        "args": ["--watch"],
        "desc": "inbox 감시 + Claude 응답 작성",
    },
    "schedule": {
        "script": "src/runtime/scheduler_worker.py",
        "args": [],
        "desc": "만기 스케줄 실행 + outbox 응답 작성",
    },
    "email": {
        "script": "daemons/email_daemon.py",
        "args": [],
        "desc": "네이버 이메일 IMAP",
    },
    "collector": {
        "script": "daemons/collector_daemon.py",
        "args": [],
        "desc": "주식 데이터 일일 수집",
    },
    "trump": {
        "script": "daemons/trump_monitor.py",
        "args": [],
        "desc": "트럼프 Truth Social RSS 모니터",
    },
    "market-api": {
        "script": "daemons/market_api.py",
        "args": [],
        "desc": "market.db 읽기 전용 HTTP API (port 8001)",
    },
}

ALL_DAEMONS = DAEMONS


def _pid_file(name):
    return os.path.join(RUN_DIR, f"{name}.pid")


def _log_file(name):
    return os.path.join(LOG_DIR, f"{name}.log")


def _plist_path(name):
    return os.path.join(PLIST_DIR, f"{PLIST_PREFIX}.{name}.plist")


def _launchd_domain():
    return f"gui/{os.getuid()}"


def _app_path(name):
    return os.path.join(APP_DIR, f"{PLIST_PREFIX}.{name}.app")


def _app_executable(name):
    return os.path.join(_app_path(name), "Contents", "MacOS", name)


def _build_app(name, force=False):
    """FDA용 네이티브 Swift .app 번들 생성. 이미 있으면 스킵."""
    app = _app_path(name)
    if os.path.exists(app) and not force:
        return app

    script = os.path.join(PROJECT_ROOT, ALL_DAEMONS[name]["script"])
    args = ALL_DAEMONS[name].get("args", [])
    log = _log_file(name)
    bundle_id = f"{PLIST_PREFIX}.{name}"
    swift_args = json.dumps(["-u", script] + args, ensure_ascii=False)
    os.makedirs(os.path.dirname(log), exist_ok=True)
    open(log, "a").close()

    # 디렉토리 구조
    macos_dir = os.path.join(app, "Contents", "MacOS")
    os.makedirs(macos_dir, exist_ok=True)

    # Swift 소스 — Python 스크립트를 자식 프로세스로 실행
    swift_src = textwrap.dedent(f"""\
        import Foundation
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "{PYTHON}")
        proc.arguments = {swift_args}
        proc.currentDirectoryURL = URL(fileURLWithPath: "{PROJECT_ROOT}")
        let log = FileHandle(forWritingAtPath: "{log}") ?? FileHandle.nullDevice
        log.seekToEndOfFile()
        proc.standardOutput = log
        proc.standardError = log
        signal(SIGTERM, SIG_IGN)
        let src = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
        src.setEventHandler {{ proc.terminate(); exit(0) }}
        src.resume()
        do {{ try proc.run(); proc.waitUntilExit() }}
        catch {{ fputs("launch failed: \\(error)\\n", stderr); exit(1) }}
    """)

    swift_file = os.path.join(macos_dir, "main.swift")
    with open(swift_file, "w") as f:
        f.write(swift_src)

    # 컴파일
    exe = _app_executable(name)
    subprocess.run(["swiftc", swift_file, "-o", exe], check=True)
    os.remove(swift_file)

    # Info.plist
    info = {
        "CFBundleIdentifier": bundle_id,
        "CFBundleName": f"Alf {name}",
        "CFBundleExecutable": name,
        "CFBundleVersion": "1.0",
        "CFBundlePackageType": "APPL",
        "LSBackgroundOnly": True,
    }
    with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
        plistlib.dump(info, f)

    # Ad-hoc 코드 서명
    subprocess.run(["codesign", "--force", "--sign", "-", app], check=True)
    return app


def _read_pid(name):
    path = _pid_file(name)
    if not os.path.exists(path):
        return None
    pid = int(open(path).read().strip())
    try:
        os.kill(pid, 0)
        return pid
    except OSError:
        os.remove(path)
        return None


def _launchd_status(name):
    label = f"{PLIST_PREFIX}.{name}"
    r = subprocess.run(["launchctl", "list", label], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if '"PID"' in line or line.strip().startswith('"PID" ='):
            pid = "".join(c for c in line if c.isdigit())
            return int(pid) if pid else "loaded"
    return "loaded"


def _launchctl_bootstrap(plist_path):
    domain = _launchd_domain()
    subprocess.run(
        ["launchctl", "bootout", domain, plist_path],
        capture_output=True,
        text=True,
    )
    return subprocess.run(
        ["launchctl", "bootstrap", domain, plist_path],
        capture_output=True,
        text=True,
    )


def _launchctl_bootout(plist_path):
    return subprocess.run(
        ["launchctl", "bootout", _launchd_domain(), plist_path],
        capture_output=True,
        text=True,
    )


def _resolve_names(name):
    if name == "all":
        return list(DAEMONS.keys())
    if name not in ALL_DAEMONS:
        print(f"알 수 없는 데몬: {name} (가능: {', '.join(ALL_DAEMONS)})")
        sys.exit(1)
    return [name]


# --- 서브커맨드 ---

def cmd_start(args):
    os.makedirs(RUN_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    for name in _resolve_names(args.name):
        if _read_pid(name):
            print(f"[{name}] 이미 실행 중 (PID {_read_pid(name)})")
            continue
        script = os.path.join(PROJECT_ROOT, ALL_DAEMONS[name]["script"])
        cmd = [PYTHON, "-u", script] + ALL_DAEMONS[name].get("args", [])
        log = open(_log_file(name), "a")
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=log, stderr=log,
        )
        with open(_pid_file(name), "w") as f:
            f.write(str(proc.pid))
        print(f"[{name}] 시작 (PID {proc.pid}) — 로그: {_log_file(name)}")


def cmd_stop(args):
    for name in _resolve_names(args.name):
        pid = _read_pid(name)
        if not pid:
            print(f"[{name}] 실행 중이 아님")
            continue
        os.kill(pid, signal.SIGTERM)
        os.remove(_pid_file(name))
        print(f"[{name}] 정지 (PID {pid})")


def cmd_status(args):
    names = _resolve_names(args.name) if args.name else list(DAEMONS.keys())
    for name in names:
        d = ALL_DAEMONS[name]
        dev_pid = _read_pid(name)
        ld = _launchd_status(name)
        if dev_pid:
            state = f"dev 실행 중 (PID {dev_pid})"
        elif isinstance(ld, int):
            state = f"launchd 실행 중 (PID {ld})"
        elif ld:
            state = "launchd loaded (프로세스 없음)"
        elif os.path.exists(_plist_path(name)):
            state = "launchd 등록됨 (상태 조회 제한)"
        else:
            state = "정지"
        print(f"  {name:8s} {state:40s} {d['desc']}")


def cmd_logs(args):
    log = _log_file(args.name)
    if not os.path.exists(log):
        print(f"로그 없음: {log}")
        return
    flag = ["-f"] if args.f else ["-30"]
    os.execvp("tail", ["tail"] + flag + [log])


def cmd_install(args):
    os.makedirs(PLIST_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    names = _resolve_names(args.name)
    fda_apps = []
    for name in names:
        app = _build_app(name, force=True)
        label = f"{PLIST_PREFIX}.{name}"
        bundle_id = f"{PLIST_PREFIX}.{name}"
        plist = {
            "Label": label,
            "ProgramArguments": [_app_executable(name)],
            "WorkingDirectory": PROJECT_ROOT,
            "EnvironmentVariables": {
                "PATH": "/opt/homebrew/bin:/Users/afred/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            },
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 10,
            "AssociatedBundleIdentifiers": bundle_id,
        }
        path = _plist_path(name)
        with open(path, "wb") as f:
            plistlib.dump(plist, f)
        result = _launchctl_bootstrap(path)
        if result.returncode != 0:
            print(f"[{name}] launchctl bootstrap 경고: {result.stderr.strip()}")
        fda_apps.append(app)
        print(f"[{name}] launchd 등록 완료 — {path}")
    print(f"\n전체 디스크 접근에 .app 등록 필요:")
    for app in fda_apps:
        print(f"  {app}")


def cmd_uninstall(args):
    for name in _resolve_names(args.name):
        path = _plist_path(name)
        if not os.path.exists(path):
            print(f"[{name}] plist 없음")
            continue
        result = _launchctl_bootout(path)
        if result.returncode != 0 and "No such process" not in (result.stderr or ""):
            print(f"[{name}] launchctl bootout 경고: {result.stderr.strip()}")
        os.remove(path)
        print(f"[{name}] launchd 해제 + plist 삭제")


def main():
    p = argparse.ArgumentParser(description="Alf 데몬 매니저")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("start", help="dev 모드 시작")
    s.add_argument("name", help="데몬 이름 또는 all")

    s = sub.add_parser("stop", help="dev 모드 정지")
    s.add_argument("name", help="데몬 이름 또는 all")

    s = sub.add_parser("status", help="상태 확인")
    s.add_argument("name", nargs="?", help="데몬 이름 (생략 시 전체)")

    s = sub.add_parser("logs", help="로그 보기")
    s.add_argument("name", help="데몬 이름")
    s.add_argument("-f", action="store_true", help="실시간 follow")

    s = sub.add_parser("install", help="launchd 등록 (프로덕션)")
    s.add_argument("name", help="데몬 이름 또는 all")

    s = sub.add_parser("uninstall", help="launchd 해제")
    s.add_argument("name", help="데몬 이름 또는 all")

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return

    {"start": cmd_start, "stop": cmd_stop, "status": cmd_status,
     "logs": cmd_logs, "install": cmd_install, "uninstall": cmd_uninstall}[args.cmd](args)


if __name__ == "__main__":
    main()
