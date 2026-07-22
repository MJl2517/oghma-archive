import io
import unittest

from ogma.errors import PayloadTooLargeError, ValidationError
from ogma.safe_json import load_limited_json_stream


class SafeJsonTests(unittest.TestCase):
    def test_size_depth_and_item_limits_apply_to_import_streams(self):
        with self.assertRaises(PayloadTooLargeError):
            load_limited_json_stream(io.BytesIO(b'{"long":"value"}'), maximum_bytes=4)

        nested = b'{"a":' * 34 + b"0" + b"}" * 34
        with self.assertRaises(ValidationError):
            load_limited_json_stream(io.BytesIO(nested))

        too_many = ("[" + ",".join("0" for _ in range(10_001)) + "]").encode()
        with self.assertRaises(ValidationError):
            load_limited_json_stream(io.BytesIO(too_many))

        self.assertEqual(
            load_limited_json_stream(io.BytesIO(b'{"safe":[1,2,3]}')),
            {"safe": [1, 2, 3]},
        )


if __name__ == "__main__":
    unittest.main()
