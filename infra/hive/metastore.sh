#!/bin/bash
set -euo pipefail
if [ -d /state/metastore_db ]; then
  # A directory can survive an interrupted init; verify the schema itself.
  if ! HADOOP_CLIENT_OPTS="${HADOOP_CLIENT_OPTS:-} ${SERVICE_OPTS:-}" /opt/hive/bin/schematool -dbType derby -info > /tmp/chess4f-schema-check.log 2>&1; then
    cat /tmp/chess4f-schema-check.log >&2
    echo 'Existing metastore schema is incomplete. Preserve it before recovery; refusing to skip initialization.' >&2
    exit 1
  fi
  export IS_RESUME=true
fi
exec /entrypoint.sh
