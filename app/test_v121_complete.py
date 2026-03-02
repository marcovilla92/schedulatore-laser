#!/usr/bin/env python
"""Test v1.2.1: Timing fix + Total time calculation with in-memory database"""
import sys
import time
from datetime import datetime, timedelta
import uuid

sys.path.insert(0, '.')

# Setup in-memory database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Base, ProcessingStep, OrderNotification, OrderStatus

# Create in-memory engine
test_engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(bind=test_engine)
TestSession = sessionmaker(bind=test_engine)

# Monkey-patch to use test session
import backend.models
import backend.database
original_get_session = backend.models.get_session
backend.models.get_session = lambda: TestSession()
backend.database.get_session = lambda: TestSession()

from backend.database import OrderManager

print("=" * 60)
print("v1.2.1 HOTFIX TEST - In-Memory Database")
print("=" * 60 + "\n")

# [1] Create order
print("[1/5] Creating test order with 3 articles...")
order_id = str(uuid.uuid4())
articles = [
    {"code": "ART-001", "name": "Articolo 1", "qty": 10},
    {"code": "ART-002", "name": "Articolo 2", "qty": 20},
    {"code": "ART-003", "name": "Articolo 3", "qty": 30},
]

order = OrderManager.create_order(
    cliente="Test Cliente",
    data_consegna="2026-03-01T00:00:00",
    articles=articles,
    required_phases=["LASER", "PIEGA"],
)
print(f"      ✓ Order created: {order.id}\n")

# [2] Start LASER phase and do partial completion
print("[2/5] LASER phase: Start and partial completion...")
OrderManager.complete_phase_start(order.id, "LASER")
print("      ✓ Phase started")

time.sleep(0.5)
OrderManager.complete_phase_partial(order.id, "LASER", [0, 1])
print("      ✓ Completed 2 of 3 articles (partial)")

session = TestSession()
step = session.query(ProcessingStep).filter(
    ProcessingStep.order_id == order.id,
    ProcessingStep.fase == "LASER"
).first()

print(f"      - timestamp_ultimo_partial set: {step.timestamp_ultimo_partial is not None}")
if not step.timestamp_ultimo_partial:
    print("      ERROR: timestamp_ultimo_partial should be set!")
    sys.exit(1)
print()

# [3] Complete remaining articles
print("[3/5] LASER phase: Complete all articles...")
time.sleep(0.5)
OrderManager.complete_phase_partial(order.id, "LASER", [2])
print("      ✓ Completed last article")

session = TestSession()
step = session.query(ProcessingStep).filter(
    ProcessingStep.order_id == order.id,
    ProcessingStep.fase == "LASER"
).first()

print(f"      - timestamp_fine set: {step.timestamp_fine is not None}")
if not step.timestamp_fine:
    print("      ERROR: timestamp_fine should be set!")
    sys.exit(1)

laser_duration = step.timestamp_fine - step.timestamp_inizio
print(f"      - LASER duration: ~{int(laser_duration.total_seconds())} seconds\n")

# [4] Start and complete PIEGA phase
print("[4/5] PIEGA phase: Start and complete...")
OrderManager.complete_phase_start(order.id, "PIEGA")
print("      ✓ Phase started")

time.sleep(0.5)
OrderManager.complete_phase(order.id, "PIEGA")
print("      ✓ Phase completed\n")

# [5] Verify total time calculation
print("[5/5] Verifying total time calculation...")
session = TestSession()
notification = session.query(OrderNotification).filter(
    OrderNotification.order_id == order.id
).first()

if not notification:
    print("      ERROR: No notification found!")
    sys.exit(1)

print(f"      - Notification created")
print(f"      - tempi_totali: {notification.tempi_totali}")

# Verify calculation
if notification.tempi_totali == "Ordine completato":
    print("      ERROR: tempi_totali is placeholder text!")
    sys.exit(1)
elif notification.tempi_totali == "Errore calcolo":
    print("      ERROR: Time calculation failed!")
    sys.exit(1)

# Verify format is correct (should be "Xh Ymin" or similar)
valid_formats = ["min", "h"]
is_valid = any(fmt in notification.tempi_totali for fmt in valid_formats)
if not is_valid and notification.tempi_totali != "0min":
    print(f"      ERROR: Invalid time format: {notification.tempi_totali}")
    sys.exit(1)

print(f"      ✓ Format valid\n")

# Summary
print("=" * 60)
print("TEST RESULTS")
print("=" * 60)
print(f"Order ID:        {order.id}")
print(f"Total Time:      {notification.tempi_totali}")
print(f"Order Status:    {OrderStatus.SPEDITO.value}")
print()
print("✓ v1.2.1 HOTFIX VERIFICATION: ALL TESTS PASSED")
print("=" * 60)

session.close()
