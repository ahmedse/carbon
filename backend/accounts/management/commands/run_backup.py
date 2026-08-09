# File: accounts/management/commands/run_backup.py
# Phase 1.2 — Django management command for DB backups

import subprocess
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
import shlex


class Command(BaseCommand):
    help = 'Run an automated database backup (pg_dump to compressed SQL file)'

    def handle(self, **options):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'carbon_backup_{timestamp}.sql.gz'
        backup_dir = os.path.join(settings.BASE_DIR, '..', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        filepath = os.path.join(backup_dir, filename)

        db = settings.DATABASES['default']
        env = os.environ.copy()
        if 'PASSWORD' in db:
            env['PGPASSWORD'] = db['PASSWORD']

        # pg_dump args
        args = [
            'pg_dump',
            f'--host={db.get("HOST", "localhost")}',
            f'--port={db.get("PORT", "5432")}',
            f'--username={db.get("USER", "postgres")}',
            f'--dbname={db["NAME"]}',
            '--no-owner',
            '--no-acl',
            '--compress=6',
        ]

        self.stdout.write(f'Starting backup: {filepath}')

        try:
            # Create backup record
            from accounts.models import BackupRecord, BackupConfig
            record = BackupRecord.objects.create(
                filename=filename, status='running', location=filepath,
            )

            with open(filepath, 'wb') as f:
                result = subprocess.run(
                    args, stdout=f, stderr=subprocess.PIPE,
                    env=env, timeout=600,
                )

            if result.returncode == 0:
                size = os.path.getsize(filepath)
                record.status = 'success'
                record.size_bytes = size
                record.completed_at = datetime.now()
                record.save()

                cfg = BackupConfig.load()
                cfg.last_backup_at = datetime.now()
                cfg.last_backup_size_bytes = size
                cfg.save(update_fields=['last_backup_at', 'last_backup_size_bytes'])

                self.stdout.write(self.style.SUCCESS(f'Backup complete: {filename} ({size} bytes)'))

                # Cleanup old backups
                from datetime import timedelta
                cutoff = datetime.now() - timedelta(days=cfg.retention_days)
                for old in BackupRecord.objects.filter(
                    status='success', started_at__lt=cutoff
                ):
                    old_path = old.location
                    if old_path and os.path.exists(old_path):
                        os.remove(old_path)
                    old.delete()
                self.stdout.write(f'Cleaned up backups older than {cutoff:%Y-%m-%d}')
            else:
                error = result.stderr.decode('utf-8', errors='replace')
                record.status = 'failed'
                record.error_message = error
                record.completed_at = datetime.now()
                record.save()
                self.stderr.write(f'Backup failed: {error}')

        except Exception as exc:
            self.stderr.write(f'Backup error: {exc}')
            try:
                record.status = 'failed'
                record.error_message = str(exc)
                record.completed_at = datetime.now()
                record.save()
            except Exception:
                pass

        # Optional S3 upload
        cfg = BackupConfig.load()
        if cfg.s3_bucket:
            self.stdout.write(f'Uploading to s3://{cfg.s3_bucket}/{cfg.s3_path}{filename} …')
            s3_cmd = f'aws s3 cp {shlex.quote(filepath)} s3://{cfg.s3_bucket}/{cfg.s3_path}{filename}'
            try:
                subprocess.run(s3_cmd, shell=True, check=True, timeout=120)
                self.stdout.write(self.style.SUCCESS('S3 upload complete'))
            except Exception as exc:
                self.stderr.write(f'S3 upload failed: {exc}')
