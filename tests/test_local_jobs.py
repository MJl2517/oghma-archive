import threading
import time
import unittest

from ogma.errors import ConflictError
from ogma.jobs import LocalJobBroker


class LocalJobTests(unittest.TestCase):
    def test_broker_is_single_flight_and_returns_sanitized_failure(self):
        broker = LocalJobBroker()
        release = threading.Event()
        started = threading.Event()

        def blocking_operation():
            started.set()
            release.wait(2)
            return {"ok": True}

        job_id = broker.start("picker", blocking_operation)
        self.assertTrue(started.wait(1))
        with self.assertRaises(ConflictError):
            broker.start("second", lambda: None)
        release.set()

        deadline = time.monotonic() + 2
        status = broker.status(job_id)
        while status["state"] not in {"succeeded", "failed"} and time.monotonic() < deadline:
            time.sleep(0.01)
            status = broker.status(job_id)
        self.assertEqual(status["state"], "succeeded")
        self.assertEqual(status["result"], {"ok": True})

        failed_id = broker.start(
            "failure",
            lambda: (_ for _ in ()).throw(RuntimeError(r"C:\private\secret")),
        )
        deadline = time.monotonic() + 2
        failed = broker.status(failed_id)
        while failed["state"] not in {"succeeded", "failed"} and time.monotonic() < deadline:
            time.sleep(0.01)
            failed = broker.status(failed_id)
        self.assertEqual(failed["state"], "failed")
        self.assertNotIn("private", str(failed))
        self.assertNotIn("secret", str(failed))


if __name__ == "__main__":
    unittest.main()
