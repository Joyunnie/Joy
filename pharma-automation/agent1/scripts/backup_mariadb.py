#!/usr/bin/env python3
"""PM+20 MariaDB Cold Backup Script.

Windows-only. Stops the MariaDB service, copies the data directory,
verifies checksums, optionally compresses, then restarts the service.
"""

import argparse
import hashlib
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml")
    sys.exit(1)

try:
    import psutil
except ImportError:
    print("ERROR: psutil is required. Install with: pip install psutil")
    sys.exit(1)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("backup_mariadb")

STOP_TIMEOUT = 300  # seconds


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_admin():
    """Check if running as Administrator (Windows)."""
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            logger.error("This script requires Administrator privileges.")
            sys.exit(1)
    except AttributeError:
        pass


def acquire_lock(lock_path: str) -> bool:
    lock_file = Path(lock_path)
    if lock_file.exists():
        logger.error("Lock file exists: %s — another backup may be running.", lock_path)
        return False
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock(lock_path: str):
    lock_file = Path(lock_path)
    if lock_file.exists():
        lock_file.unlink()


def check_disk_space(output_dir: str, min_gb: float) -> bool:
    usage = shutil.disk_usage(output_dir)
    free_gb = usage.free / (1024 ** 3)
    if free_gb < min_gb:
        logger.error("Insufficient disk space: %.1f GB free, %.1f GB required.", free_gb, min_gb)
        return False
    logger.info("Disk space OK: %.1f GB free.", free_gb)
    return True


def find_mysqld_pid(data_dir: str):
    """Find mysqld process by matching data directory."""
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["name"] and "mysqld" in proc.info["name"].lower():
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def stop_service(service_name: str, data_dir: str, force: bool, dry_run: bool) -> bool:
    """Stop the MariaDB Windows service and wait for mysqld to exit."""
    pid = find_mysqld_pid(data_dir)
    if pid:
        logger.info("Found mysqld PID: %d", pid)
    else:
        logger.warning("mysqld process not found — service may already be stopped.")
        return True

    if dry_run:
        logger.info("[DRY-RUN] Would stop service: %s", service_name)
        return True

    logger.info("Stopping service: %s", service_name)
    subprocess.run(["net", "stop", service_name], check=False)

    # Wait for PID to disappear
    elapsed = 0
    poll_interval = 2
    while elapsed < STOP_TIMEOUT:
        if not psutil.pid_exists(pid):
            logger.info("Service stopped (PID %d gone) after %ds.", pid, elapsed)
            return True
        time.sleep(poll_interval)
        elapsed += poll_interval

    # Timeout — handle based on --force flag
    if force:
        logger.warning("Service did not stop within %ds. Using taskkill /F.", STOP_TIMEOUT)
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False)
        time.sleep(3)
        if not psutil.pid_exists(pid):
            logger.warning("Forcefully killed PID %d.", pid)
            return True
        logger.error("Failed to kill PID %d even with taskkill /F.", pid)
        return False
    else:
        logger.error(
            "Service did not stop within %ds. ABORTING. Use --force to forcefully kill.",
            STOP_TIMEOUT,
        )
        return False


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_and_verify(
    data_dir: str, dest_dir: str, force_kill_used: bool, dry_run: bool
) -> bool:
    """Copy data directory and verify with SHA-256 checksums."""
    src = Path(data_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "_unclean" if force_kill_used else ""
    dest_name = f"backup_{timestamp}{suffix}"
    dest = Path(dest_dir) / dest_name

    if dry_run:
        logger.info("[DRY-RUN] Would copy %s → %s", src, dest)
        return True

    logger.info("Copying %s → %s", src, dest)
    shutil.copytree(str(src), str(dest))

    # Verify checksums
    logger.info("Verifying checksums...")
    mismatch = False
    for src_file in src.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src)
        dst_file = dest / rel
        if not dst_file.exists():
            logger.critical("MISSING in backup: %s", rel)
            mismatch = True
            continue
        src_hash = compute_sha256(src_file)
        dst_hash = compute_sha256(dst_file)
        if src_hash != dst_hash:
            logger.critical("CHECKSUM MISMATCH: %s", rel)
            mismatch = True

    if mismatch:
        corrupted = dest.with_name(dest.name + "_corrupted")
        dest.rename(corrupted)
        logger.critical("Backup corrupted! Renamed to: %s", corrupted)
        return False

    logger.info("Checksum verification passed.")
    return True


def compress_backup(dest_dir: str, compress_format: str, dry_run: bool):
    """Compress the most recent backup directory."""
    dest = Path(dest_dir)
    backups = sorted(dest.glob("backup_*"), reverse=True)
    if not backups:
        return

    latest = backups[0]
    if not latest.is_dir():
        return

    if dry_run:
        logger.info("[DRY-RUN] Would compress %s as %s", latest, compress_format)
        return

    logger.info("Compressing %s (%s)...", latest.name, compress_format)
    if compress_format == "zip":
        archive = shutil.make_archive(str(latest), "zip", str(dest), latest.name)
    else:
        archive = shutil.make_archive(str(latest), "gztar", str(dest), latest.name)

    # Remove uncompressed directory after successful compression
    shutil.rmtree(str(latest))
    logger.info("Compressed: %s", archive)


def start_service(service_name: str, dry_run: bool) -> bool:
    """Start the MariaDB Windows service."""
    if dry_run:
        logger.info("[DRY-RUN] Would start service: %s", service_name)
        return True

    logger.info("Starting service: %s", service_name)
    result = subprocess.run(["net", "start", service_name], check=False)
    if result.returncode != 0:
        logger.error("Failed to start service: %s", service_name)
        return False

    # Poll for mysqld process to appear
    elapsed = 0
    while elapsed < 60:
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and "mysqld" in proc.info["name"].lower():
                    logger.info("Service started successfully (mysqld running).")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(2)
        elapsed += 2

    logger.warning("Service start command succeeded but mysqld not detected after 60s.")
    return True


def cleanup_old_backups(output_dir: str, retention_days: int, min_count: int, dry_run: bool):
    """Remove backups older than retention_days, keeping at least min_count."""
    dest = Path(output_dir)
    backups = sorted(dest.glob("backup_*"), reverse=True)

    if len(backups) <= min_count:
        logger.info("Only %d backup(s), keeping all (min_count=%d).", len(backups), min_count)
        return

    cutoff = datetime.now() - timedelta(days=retention_days)

    for backup in backups[min_count:]:
        # Extract timestamp from name: backup_YYYYMMDD_HHMMSS...
        name = backup.name.replace("backup_", "").split("_unclean")[0].split("_corrupted")[0]
        try:
            parts = name.split(".")  # remove extension if compressed
            ts_str = parts[0] if len(parts[0]) == 15 else parts[0][:15]
            ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
        except ValueError:
            continue

        if ts < cutoff:
            if dry_run:
                logger.info("[DRY-RUN] Would remove old backup: %s", backup)
            else:
                if backup.is_dir():
                    shutil.rmtree(str(backup))
                else:
                    backup.unlink()
                logger.info("Removed old backup: %s", backup)


def main():
    parser = argparse.ArgumentParser(description="PM+20 MariaDB Cold Backup")
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without making changes")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force kill mysqld if graceful stop fails (creates _unclean backup)",
    )
    args = parser.parse_args()

    # Platform check
    if platform.system() != "Windows":
        print("This script requires Windows (PM+20 runs on Windows only). Exiting.")
        sys.exit(0)

    config = load_config(args.config)
    pm20 = config["pm20"]
    backup_cfg = config["backup"]

    service_name = pm20["service_name"]
    data_dir = pm20["data_dir"]
    output_dir = backup_cfg["output_dir"]
    lock_path = backup_cfg["lock_file"]

    # Pre-flight checks
    check_admin()

    if not acquire_lock(lock_path):
        sys.exit(1)

    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        if not check_disk_space(output_dir, backup_cfg["min_disk_space_gb"]):
            sys.exit(1)

        # Stop service
        force_kill_used = False
        if not stop_service(service_name, data_dir, args.force, args.dry_run):
            if not args.force:
                logger.error("ABORT: Service did not stop. Use --force to override.")
                sys.exit(1)

        # If force was used and service eventually stopped via taskkill
        if args.force:
            force_kill_used = True

        # Copy and verify
        if not copy_and_verify(data_dir, output_dir, force_kill_used, args.dry_run):
            logger.error("Backup verification failed!")
            # Still try to restart service
            start_service(service_name, args.dry_run)
            sys.exit(1)

        # Optional compression
        if backup_cfg.get("compress", False):
            compress_backup(output_dir, backup_cfg.get("compress_format", "zip"), args.dry_run)

        # Restart service
        start_service(service_name, args.dry_run)

        # Retention cleanup
        cleanup_old_backups(
            output_dir,
            backup_cfg.get("retention_days", 30),
            backup_cfg.get("retention_min_count", 3),
            args.dry_run,
        )

        logger.info("Backup completed successfully.")

    finally:
        release_lock(lock_path)


if __name__ == "__main__":
    main()
