import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Create and verify a consistent SQLite backup, then prune old backups.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--destination',
            default=os.environ.get('UNIKIT_BACKUP_DIR', str(settings.BASE_DIR / 'backups')),
            help='Directory that will receive the backup files.',
        )
        parser.add_argument('--keep', type=int, default=30, help='Number of backups to retain.')

    def handle(self, *args, **options):
        if connection.vendor != 'sqlite':
            raise CommandError('This backup command currently supports SQLite only.')
        if options['keep'] < 1:
            raise CommandError('--keep must be at least 1.')

        source_path = Path(settings.DATABASES['default']['NAME']).resolve()
        destination_dir = Path(options['destination']).expanduser().resolve()
        destination_dir.mkdir(parents=True, exist_ok=True)

        if not source_path.exists():
            raise CommandError(f'Database does not exist: {source_path}')
        if destination_dir == source_path.parent:
            self.stderr.write(self.style.WARNING(
                'The backup is beside the live database. Copy backups to a separate device for recovery.'
            ))

        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup_path = destination_dir / f'unikit-{timestamp}.sqlite3'

        connection.close()
        try:
            with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as target:
                source.backup(target)
            with sqlite3.connect(backup_path) as verified:
                result = verified.execute('PRAGMA integrity_check').fetchone()[0]
        except sqlite3.Error as exc:
            backup_path.unlink(missing_ok=True)
            raise CommandError(f'Backup failed: {exc}') from exc

        if result != 'ok':
            backup_path.unlink(missing_ok=True)
            raise CommandError(f'Backup integrity check failed: {result}')

        digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()
        checksum_path = backup_path.with_suffix('.sqlite3.sha256')
        checksum_path.write_text(f'{digest}  {backup_path.name}\n', encoding='ascii')

        backups = sorted(destination_dir.glob('unikit-*.sqlite3'), reverse=True)
        for expired in backups[options['keep']:]:
            expired.unlink(missing_ok=True)
            expired.with_suffix('.sqlite3.sha256').unlink(missing_ok=True)

        self.stdout.write(self.style.SUCCESS(f'Verified backup created: {backup_path}'))
