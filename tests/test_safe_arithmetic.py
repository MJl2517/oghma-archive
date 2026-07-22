import unittest

from ogma.safe_arithmetic import UnsafeArithmeticExpression, evaluate_arithmetic


class SafeArithmeticTests(unittest.TestCase):
    def test_supported_arithmetic(self) -> None:
        self.assertEqual(14, evaluate_arithmetic("2 + 3 * 4"))
        self.assertEqual(3, evaluate_arithmetic("11 // 3"))
        self.assertEqual(-5, evaluate_arithmetic("-(2 + 3)"))

    def test_power_calls_names_and_attributes_are_forbidden(self) -> None:
        for expression in (
            "2 ** 1000000",
            "__import__('os').system('whoami')",
            "(1).__class__",
            "[1, 2, 3]",
        ):
            with self.subTest(expression=expression):
                with self.assertRaises(UnsafeArithmeticExpression):
                    evaluate_arithmetic(expression)

    def test_length_depth_node_and_value_limits(self) -> None:
        for expression in (
            "1+" * 130 + "1",
            "-" * 17 + "1",
            "+".join(["1"] * 70),
            "1000000000 * 2",
        ):
            with self.subTest(expression=expression[:40]):
                with self.assertRaises(UnsafeArithmeticExpression):
                    evaluate_arithmetic(expression)

    def test_nan_infinity_and_division_by_zero_are_forbidden(self) -> None:
        for expression in ("1e999", "0 / 0", "1 / 0"):
            with self.subTest(expression=expression):
                with self.assertRaises(UnsafeArithmeticExpression):
                    evaluate_arithmetic(expression)


if __name__ == "__main__":
    unittest.main()
