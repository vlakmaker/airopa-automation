#!/bin/bash
# Railway startup script

echo "Initializing database..."
python -m airopa_automation.api.init_db <<EOF
no
EOF

echo "Starting API server..."
exec uvicorn airopa_automation.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
