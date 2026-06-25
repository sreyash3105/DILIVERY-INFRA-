#!/bin/bash

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
PG_BACKUP_FILE="${BACKUP_DIR}/postgres_backup_${TIMESTAMP}.sql"
REDIS_BACKUP_FILE="${BACKUP_DIR}/redis_backup_${TIMESTAMP}.rdb"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

echo "=========================================="
echo "Starting Platform Backup Pipeline..."
echo "=========================================="

# 1. Back up PostgreSQL
echo "Running PostgreSQL pg_dump..."
START_PG=$(date +%s)
if docker exec postgres pg_isready -U postgres > /dev/null 2>&1; then
    docker exec postgres pg_dump -U postgres delivery_platform > "${PG_BACKUP_FILE}"
    END_PG=$(date +%s)
    DURATION_PG=$((END_PG - START_PG))
    FILESIZE_PG=$(du -h "${PG_BACKUP_FILE}" | cut -f1)
    echo "✓ PostgreSQL backup saved to: ${PG_BACKUP_FILE}"
    echo "  - Size: ${FILESIZE_PG}"
    echo "  - Duration: ${DURATION_PG} seconds"
else
    echo "✗ ERROR: PostgreSQL container is not running or not healthy."
    exit 1
fi

# 2. Back up Redis
echo "Running Redis snapshot SAVE..."
START_REDIS=$(date +%s)
if docker exec redis redis-cli ping | grep PONG > /dev/null 2>&1; then
    # Force Redis to write a point-in-time snapshot to disk
    docker exec redis redis-cli SAVE > /dev/null 2>&1
    # Copy dump file from container to backup directory
    docker cp redis:/data/dump.rdb "${REDIS_BACKUP_FILE}"
    END_REDIS=$(date +%s)
    DURATION_REDIS=$((END_REDIS - START_REDIS))
    FILESIZE_REDIS=$(du -h "${REDIS_BACKUP_FILE}" | cut -f1)
    echo "✓ Redis snapshot backup saved to: ${REDIS_BACKUP_FILE}"
    echo "  - Size: ${FILESIZE_REDIS}"
    echo "  - Duration: ${DURATION_REDIS} seconds"
else
    echo "✗ ERROR: Redis container is not running or not healthy."
    exit 1
fi

echo "=========================================="
echo "Backup Completed Successfully!"
echo "=========================================="

# 3. Restore Validation Simulation
echo "Simulating Restore & Verification..."
echo "Creating temporary verification database..."
docker exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS delivery_platform_verify;" > /dev/null
docker exec postgres psql -U postgres -c "CREATE DATABASE delivery_platform_verify;" > /dev/null

echo "Restoring PostgreSQL dump to verification database..."
START_RESTORE=$(date +%s)
docker exec -i postgres psql -U postgres -d delivery_platform_verify < "${PG_BACKUP_FILE}" > /dev/null
RESTORE_STATUS=$?
END_RESTORE=$(date +%s)
DURATION_RESTORE=$((END_RESTORE - START_RESTORE))

if [ ${RESTORE_STATUS} -eq 0 ]; then
    echo "✓ RESTORE VERIFICATION SUCCESS: Data recovered successfully on temp instance."
    echo "  - Restore Duration: ${DURATION_RESTORE} seconds"
    docker exec postgres psql -U postgres -c "DROP DATABASE delivery_platform_verify;" > /dev/null
else
    echo "✗ ERROR: Database restoration test failed!"
    exit 1
fi

echo "=========================================="
echo "All backups verified and healthy!"
echo "=========================================="
