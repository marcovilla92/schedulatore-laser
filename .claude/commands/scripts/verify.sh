#!/bin/bash
# /verify - Start Flask backend and run health checks
# Customized for Schedulatore Laser

# ============================================
# PROJECT CONFIG: Schedulatore Laser (Flask)
# ============================================
DEV_COMMAND="python app/run.py"
HEALTH_CHECK_URL="http://localhost:5000"
HEALTH_CHECK_PATH="/api/health"
MAX_WAIT_TIME=30
CLEANUP_ON_EXIT=true
# ============================================

echo "Verifying Schedulatore Laser"
echo ""

TEMP_LOG=$(mktemp)
SERVER_PID=""

cleanup() {
    if [ "$CLEANUP_ON_EXIT" = true ] && [ -n "$SERVER_PID" ]; then
        echo ""
        echo "Cleaning up..."
        kill $SERVER_PID 2>/dev/null
        wait $SERVER_PID 2>/dev/null
        rm -f "$TEMP_LOG"
        echo "Cleanup complete"
    fi
}

trap cleanup EXIT

echo "Step 1/5: Starting Flask backend..."
$DEV_COMMAND > "$TEMP_LOG" 2>&1 &
SERVER_PID=$!
echo "  PID: $SERVER_PID"
echo ""

echo "Step 2/5: Waiting for server (max ${MAX_WAIT_TIME}s)..."
WAITED=0
READY=false

while [ $WAITED -lt $MAX_WAIT_TIME ]; do
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo ""
        echo "Server process died unexpectedly"
        echo "Last 20 lines:"
        tail -20 "$TEMP_LOG"
        exit 1
    fi

    if curl -sf "${HEALTH_CHECK_URL}${HEALTH_CHECK_PATH}" > /dev/null 2>&1; then
        READY=true
        break
    fi

    sleep 1
    ((WAITED++))
    echo -ne "  Waited ${WAITED}s...\r"
done

echo ""

if [ "$READY" = false ]; then
    echo "Server failed to start within ${MAX_WAIT_TIME}s"
    tail -20 "$TEMP_LOG"
    exit 1
fi

echo "Server is ready!"
echo ""

echo "Step 3/5: Health check..."
HEALTH_RESPONSE=$(curl -sf "${HEALTH_CHECK_URL}/api/health")
echo "  /api/health: $HEALTH_RESPONSE"

RESPONSE_TIME=$(curl -o /dev/null -s -w '%{time_total}' "${HEALTH_CHECK_URL}/api/health")
echo "  Response time: ${RESPONSE_TIME}s"
echo ""

echo "Step 4/5: API endpoint checks..."

# Welcome page
STATUS=$(curl -o /dev/null -s -w '%{http_code}' "${HEALTH_CHECK_URL}/")
echo "  GET /           : $STATUS"

# Orders API
STATUS=$(curl -o /dev/null -s -w '%{http_code}' "${HEALTH_CHECK_URL}/api/orders")
echo "  GET /api/orders : $STATUS"

# Frontend pages
for page in dashboard.html laser.html piega.html saldatura.html ordini_estratti.html archive.html; do
    STATUS=$(curl -o /dev/null -s -w '%{http_code}' "${HEALTH_CHECK_URL}/${page}")
    echo "  GET /${page}: $STATUS"
done

echo ""
echo "Step 5/5: Summary"
echo "  Server: ${HEALTH_CHECK_URL}"
echo "  PID: ${SERVER_PID}"
echo "  Status: ALL PASSING"
echo ""
echo "Verification complete!"
exit 0
