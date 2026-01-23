import unittest
from datetime import datetime, timezone

from gdrivemgr.util.time import (
    normalize_dt,
    now_utc,
    parse_rfc3339,
    same_instant,
    to_rfc3339,
)


class TestUtilTime(unittest.TestCase):
    def test_now_utc_is_tz_aware(self) -> None:
        dt = now_utc()
        self.assertIsNotNone(dt.tzinfo)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_normalize_dt_rejects_naive(self) -> None:
        naive = datetime(2025, 1, 1, 12, 0, 0)
        with self.assertRaises(ValueError):
            normalize_dt(naive)

    def test_parse_rfc3339_z(self) -> None:
        dt = parse_rfc3339("2025-01-01T12:34:56Z")
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(dt, datetime(2025, 1, 1, 12, 34, 56, tzinfo=timezone.utc))

    def test_parse_rfc3339_fractional_z(self) -> None:
        dt = parse_rfc3339("2025-01-01T12:34:56.123456Z")
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(
            dt, datetime(2025, 1, 1, 12, 34, 56, 123456, tzinfo=timezone.utc)
        )

    def test_parse_rfc3339_offset_converts_to_utc(self) -> None:
        dt = parse_rfc3339("2025-01-01T12:34:56+09:00")
        self.assertEqual(dt.tzinfo, timezone.utc)
        # 12:34:56 JST == 03:34:56 UTC
        self.assertEqual(dt, datetime(2025, 1, 1, 3, 34, 56, tzinfo=timezone.utc))

    def test_to_rfc3339_outputs_z(self) -> None:
        dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        s = to_rfc3339(dt)
        self.assertTrue(s.endswith("Z"))

    def test_same_instant(self) -> None:
        a = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        b = datetime(2025, 1, 1, 21, 0, 0, tzinfo=timezone.utc)
        self.assertFalse(same_instant(a, b))

        c = parse_rfc3339("2025-01-01T12:00:00Z")
        self.assertTrue(same_instant(a, c))
