from __future__ import annotations

#!/usr/bin/env python3
"""PM+20 SQL Server Hot Backup Script.

Windows-only. Uses SQL Server BACKUP DATABASE command (hot backup, no service stop).
"""

import argparse
import logging
import os
import platform
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml")
    sys.exit(1)

try:
    import pymssql
except ImportError:
    print("ERROR: pymssql is required. Install with: pip install pymssql")
    sys.exit(1)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("backup_sqlserver")


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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


def backup_database(pm20_cfg: dict, output_path: str, dry_run: bool) -> bool:
    """SQL Server BACKUP DATABASE 실행."""
    instance = pm20_cfg.get("instance", r".\PMPLUS20")
    database = pm20_cfg.get("database", "PM_MAIN")
    auth = pm20_cfg.get("auth", "windows")

    if dry_run:
        logger.info("[DRY-RUN] Would backup %s to %s", database, output_path)
        return True

    logger.info("Backing up %s to %s", database, output_path)

    kwargs = {"server": instance, "database": "master"}
    if auth == "sql":
        kwargs["user"] = pm20_cfg.get("username", "sa")
        pw_env = pm20_cfg.get("password_env", "PM20_DB_PASSWORD")
        kwargs["password"] = os.environ.get(pw_env, "")

    try:
        conn = pymssql.connect(**kwargs)
        cursor = conn.cursor()

        # BACKUP DATABASE with compression and checksum
        sql = (
            f"BACKUP DATABASE [{database}] "
            f"TO DISK = N'{output_path}' "
            f"WITH INIT, COMPRESSION, CHECKSUM"
        )
        cursor.execute(sql)
        # BACKUP can return multiple result sets
        while cursor.nextset():
            pass
        conn.close()
        logger.info("Backup completed: %s", output_path)
        return True

    except pymssql.Error as e:
        logger.error("Backup failed: %s", e)
        return False


def verify_backup(pm20_cfg: dict, backup_path: str, dry_run: bool) -> bool:
    """RESTORE VERIFYONLY로 백업 파일 무결성 검증."""
    instance = pm20_cfg.get("instance", r".\PMPLUS20")
    auth = pm20_cfg.get("auth", "windows")

    if dry_run:
        logger.info("[DRY-RUN] Would verify backup: %s", backup_path)
        return True

    logger.info("Verifying backup: %s", backup_path)

    kwargs = {"server": instance, "database": "master"}
    if auth == "sql":
        kwargs["user"] = pm20_cfg.get("username", "sa")
        pw_env = pm20_cfg.get("password_env", "PM20_DB_PASSWORD")
        kwargs["password"] = os.environ.get(pw_env, "")

    try:
        conn = pymssql.connect(**kwargs)
        cursor = conn.cursor()
        sql = f"RESTORE VERIFYONLY FROM DISK = N'{backup_path}' WITH CHECKSUM"
        cursor.execute(sql)
        while cursor.nextset():
            pass
        conn.close()
        logger.info("Backup verification passed.")
        return True

    except pymssql.Error as e:
        logger.error("Backup verification failed: %s", e)
        return False


def cleanup_old_backups(output_dir: str, retention_days: int, min_count: int, dry_run: bool):
    """Remove backups older than retention_days, keeping at least min_count."""
    dest = Path(output_dir)
    backups = sorted(dest.glob("backup_*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)

    if len(backups) <= min_count:
        logger.info("Only %d backup(s), keeping all (min_count=%d).", len(backups), min_count)
        return

    cutoff = datetime.now() - timedelta(days=retention_days)

    for backup in backups[min_count:]:
        name = backup.stem.replace("backup_", "")
        try:
            ts = datetime.strptime(name[:15], "%Y%m%d_%H%M%S")
        except ValueError:
            continue

        if ts < cutoff:
            if dry_run:
                logger.info("[DRY-RUN] Would remove old backup: %s", backup)
            else:
                backup.unlink()
                logger.info("Removed old backup: %s", backup)


def main():
    parser = argparse.ArgumentParser(description="PM+20 SQL Server Hot Backup")
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without making changes")
    args = parser.parse_args()

    # Platform check
    if platform.system() != "Windows":
        print("This script requires Windows (PM+20 runs on Windows only). Exiting.")
        sys.exit(0)

    config = load_config(args.config)
    pm20_cfg = config["pm20"]
    backup_cfg = config["backup"]

    output_dir = backup_cfg["output_dir"]
    lock_path = backup_cfg["lock_file"]

    if not acquire_lock(lock_path):
        sys.exit(1)

    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        if not check_disk_space(output_dir, backup_cfg["min_disk_space_gb"]):
            sys.exit(1)

        # Create backup file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = str(Path(output_dir) / f"backup_{timestamp}.bak")

        # Backup (hot — no service stop needed)
        if not backup_database(pm20_cfg, backup_path, args.dry_run):
            logger.error("Backup failed!")
            sys.exit(1)

        # Verify
        if not verify_backup(pm20_cfg, backup_path, args.dry_run):
            logger.error("Backup verification failed!")
            # Rename to indicate potential corruption
            bad_path = backup_path.replace(".bak", "_unverified.bak")
            if not args.dry_run:
                Path(backup_path).rename(bad_path)
            sys.exit(1)

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
