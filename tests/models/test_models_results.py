import unittest

from gdrivemgr.models import OperationResult, SyncResult


class TestResults(unittest.TestCase):
    def test_operation_result_defaults(self) -> None:
        r = OperationResult(op_id="o1", seq=0, action="MOVE", status="success")
        self.assertEqual(r.op_id, "o1")
        self.assertIsNone(r.error_type)
        self.assertIsNone(r.result_file_id)

    def test_sync_result_defaults(self) -> None:
        r1 = OperationResult(op_id="o1", seq=0, action="MOVE", status="success")
        sr = SyncResult(status="success", stopped_op_id=None, results=[r1])
        self.assertEqual(sr.status, "success")
        self.assertEqual(sr.results[0].op_id, "o1")
        self.assertTrue(sr.snapshot_refreshed)
        self.assertEqual(sr.id_map, {})
        self.assertEqual(sr.summary, {})


if __name__ == "__main__":
    unittest.main()
