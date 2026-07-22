import unittest

from ogma.server_instance import ServerAlreadyRunningError, ServerInstanceLock


class ServerInstanceLockTests(unittest.TestCase):
    def test_second_server_for_same_port_is_rejected(self) -> None:
        first = ServerInstanceLock(51991)
        second = ServerInstanceLock(51991)
        first.acquire()
        try:
            with self.assertRaises(ServerAlreadyRunningError):
                second.acquire()
        finally:
            first.release()

        second.acquire()
        second.release()


if __name__ == "__main__":
    unittest.main()
