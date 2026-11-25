#!/bin/bash
set -euo pipefail

DB_CONTAINER=music_shop_db
DB_NAME=${1:?db name required}
DB_USER=${2:?db user required}
BACKUP_DIR="${3:-$HOME/music_shop/backups}"
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"
FILE="$BACKUP_DIR/${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql.gz"
TMP="$FILE.tmp"
trap 'rm -f "$TMP"' EXIT

# pipefail: если pg_dump упадёт, упадёт и весь скрипт
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists | gzip > "$TMP"

# проверки: файл не пустой, архив целый, внутри дамп PostgreSQL
test -s "$TMP"
gzip -t "$TMP"
zcat "$TMP" | grep -c "PostgreSQL database dump" > /dev/null

mv "$TMP" "$FILE"
echo "Backup OK: $FILE"
ls -lh "$FILE"

# удаляем бэкапы старше KEEP_DAYS дней
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +"$KEEP_DAYS" -delete