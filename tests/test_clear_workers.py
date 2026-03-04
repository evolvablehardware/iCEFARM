"""Tests for clearWorkers (endAllReservations) and add_worker upsert behavior.

Requires the Docker PostgreSQL database to be running on port 5433.
Run with: pytest tests/test_clear_workers.py -v
"""
import os
import pytest
import psycopg

# defaults to db rather than localhost since thats the postgres test container hostname
DB_URL = os.environ.get("USBIPICE_DATABASE", "postgresql://postgres:postgres@db:5432")


@pytest.fixture
def db():
    """Provides a database connection and cleans up test data afterward."""
    conn = psycopg.connect(DB_URL)
    conn.autocommit = True
    yield conn
    # Clean up any test data
    with conn.cursor() as cur:
        cur.execute("DELETE FROM worker WHERE id LIKE 'test-worker-%'")
    conn.close()


def call_add_worker(cur, worker_id="test-worker-1", host="127.0.0.1", port=9999):
    """Helper to call the add_worker stored procedure."""
    cur.execute(
        "CALL add_worker(%s::varchar(255), %s::varchar(255), %s::int, %s::varchar(255), %s::varchar(255)[])",
        (worker_id, host, port, "0.0.0-test", ["pulsecount"])
    )


def add_device(cur, serial, worker_id, status="available"):
    """Helper to insert a device directly."""
    cur.execute(
        "INSERT INTO device (id, worker_id, device_status) VALUES (%s, %s, %s::devicestatus)",
        (serial, worker_id, status)
    )


def add_reservation(cur, device_id, client_id):
    """Helper to insert a reservation."""
    cur.execute(
        "INSERT INTO reservations (device_id, client_id, until) VALUES (%s, %s, CURRENT_TIMESTAMP + interval '1 hour')",
        (device_id, client_id)
    )


class TestAddWorkerUpsert:
    """Tests that add_worker handles re-registration gracefully."""

    def test_first_registration(self, db):
        """add_worker should succeed on first call."""
        with db.cursor() as cur:
            call_add_worker(cur, "test-worker-first")
            cur.execute("SELECT id FROM worker WHERE id = 'test-worker-first'")
            assert cur.fetchone() is not None

    def test_duplicate_registration_succeeds(self, db):
        """add_worker should succeed when called twice with the same ID (upsert)."""
        with db.cursor() as cur:
            call_add_worker(cur, "test-worker-dup")
            # Second call should NOT raise an exception
            call_add_worker(cur, "test-worker-dup")
            cur.execute("SELECT id FROM worker WHERE id = 'test-worker-dup'")
            assert cur.fetchone() is not None

    def test_upsert_updates_fields(self, db):
        """Re-registering should update host/port to new values."""
        with db.cursor() as cur:
            call_add_worker(cur, "test-worker-update", host="10.0.0.1", port=8000)
            call_add_worker(cur, "test-worker-update", host="10.0.0.2", port=9000)
            cur.execute("SELECT host, port FROM worker WHERE id = 'test-worker-update'")
            row = cur.fetchone()
            assert str(row[0]) == "10.0.0.2"
            assert row[1] == 9000

    def test_upsert_cleans_stale_devices(self, db):
        """Re-registering a worker should cascade-delete its old devices."""
        with db.cursor() as cur:
            call_add_worker(cur, "test-worker-cascade")
            add_device(cur, "test-device-stale", "test-worker-cascade")

            # Verify device exists
            cur.execute("SELECT id FROM device WHERE id = 'test-device-stale'")
            assert cur.fetchone() is not None

            # Re-register worker — should cascade-delete the device
            call_add_worker(cur, "test-worker-cascade")

            cur.execute("SELECT id FROM device WHERE id = 'test-device-stale'")
            assert cur.fetchone() is None

    def test_upsert_cleans_stale_reservations(self, db):
        """Re-registering a worker should cascade-delete its old reservations."""
        with db.cursor() as cur:
            call_add_worker(cur, "test-worker-resv")
            add_device(cur, "test-device-resv", "test-worker-resv", status="reserved")
            add_reservation(cur, "test-device-resv", "test-client")

            cur.execute("SELECT device_id FROM reservations WHERE device_id = 'test-device-resv'")
            assert cur.fetchone() is not None

            # Re-register — cascades: worker delete → device delete → reservation delete
            call_add_worker(cur, "test-worker-resv")

            cur.execute("SELECT device_id FROM reservations WHERE device_id = 'test-device-resv'")
            assert cur.fetchone() is None


class TestEndAllReservations:
    """Tests that endAllReservations (used by clearWorkers) removes reservations
    while keeping workers and devices intact."""

    def test_removes_reservations(self, db):
        """endAllReservations should delete all reservation records."""
        with db.cursor() as cur:
            call_add_worker(cur, "test-worker-endres")
            add_device(cur, "test-device-endres", "test-worker-endres", status="reserved")
            add_reservation(cur, "test-device-endres", "test-client")

            # This is what Control.clearWorkers() does
            cur.execute("DELETE FROM reservations")

            cur.execute("SELECT device_id FROM reservations WHERE device_id = 'test-device-endres'")
            assert cur.fetchone() is None

    def test_keeps_workers(self, db):
        """endAllReservations should NOT delete worker records."""
        with db.cursor() as cur:
            call_add_worker(cur, "test-worker-keep")
            add_device(cur, "test-device-keep", "test-worker-keep", status="reserved")
            add_reservation(cur, "test-device-keep", "test-client")

            cur.execute("DELETE FROM reservations")

            # Worker should still exist
            cur.execute("SELECT id FROM worker WHERE id = 'test-worker-keep'")
            assert cur.fetchone() is not None

    def test_keeps_devices(self, db):
        """endAllReservations should NOT delete device records."""
        with db.cursor() as cur:
            call_add_worker(cur, "test-worker-keepdev")
            add_device(cur, "test-device-keepdev", "test-worker-keepdev", status="reserved")
            add_reservation(cur, "test-device-keepdev", "test-client")

            cur.execute("DELETE FROM reservations")

            # Device should still exist
            cur.execute("SELECT id FROM device WHERE id = 'test-device-keepdev'")
            assert cur.fetchone() is not None

    def test_noop_when_no_reservations(self, db):
        """endAllReservations should succeed even with no reservations."""
        with db.cursor() as cur:
            call_add_worker(cur, "test-worker-noop")
            add_device(cur, "test-device-noop", "test-worker-noop")

            # Should not raise
            cur.execute("DELETE FROM reservations")

            # Worker and device should still exist
            cur.execute("SELECT id FROM worker WHERE id = 'test-worker-noop'")
            assert cur.fetchone() is not None
            cur.execute("SELECT id FROM device WHERE id = 'test-device-noop'")
            assert cur.fetchone() is not None
