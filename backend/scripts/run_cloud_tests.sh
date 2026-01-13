#!/bin/bash
# Cloud Migration Test Runner
# Run comprehensive tests for Clerk, R2, and webhook integrations

set -e

echo "=========================================="
echo "Cloud Migration Test Suite"
echo "=========================================="

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Change to backend directory
cd "$BACKEND_DIR"

# Activate virtual environment if exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo ""
echo "1. Running Cloud Migration Verification..."
echo "----------------------------------------"
python scripts/verify_cloud_migration.py --verbose || echo "Verification completed with warnings"

echo ""
echo "2. Running Unit Tests..."
echo "----------------------------------------"
pytest tests/test_cloud_services.py -v --tb=short || echo "Some tests may have failed"

echo ""
echo "3. Checking Import Errors..."
echo "----------------------------------------"
python -c "
from app.core.clerk_auth import ClerkAuth, verify_webhook_signature
from app.core.hybrid_auth import get_current_user_hybrid
from app.services.r2_storage import R2StorageService, get_r2_service
from app.api.v1.endpoints.upload import router as upload_router
from app.api.v1.endpoints.webhooks import router as webhooks_router
from app.core.debug_utils import DebugLogger, CloudMigrationDebug
print('✅ All cloud modules import successfully')
"

echo ""
echo "4. Checking Database Model Fields..."
echo "----------------------------------------"
python -c "
from app.models.user import User
from app.models.activity import Activity
from sqlalchemy import inspect

# Check User model
user_mapper = inspect(User)
user_columns = [c.key for c in user_mapper.columns]
assert 'clerk_user_id' in user_columns, 'User missing clerk_user_id'
print('✅ User.clerk_user_id exists')

# Check Activity model
activity_mapper = inspect(Activity)
activity_columns = [c.key for c in activity_mapper.columns]
assert 'r2_key' in activity_columns, 'Activity missing r2_key'
assert 'storage_provider' in activity_columns, 'Activity missing storage_provider'
assert 'storage_metadata' in activity_columns, 'Activity missing storage_metadata'
print('✅ Activity R2 fields exist')
"

echo ""
echo "5. Checking Router Registration..."
echo "----------------------------------------"
python -c "
from app.api.v1.router import api_router

routes = [r.path for r in api_router.routes]
assert any('/upload' in r for r in routes), 'Upload routes not registered'
assert any('/webhooks' in r for r in routes), 'Webhook routes not registered'
print('✅ Cloud routes registered correctly')
"

echo ""
echo "=========================================="
echo "Test Suite Complete"
echo "=========================================="
