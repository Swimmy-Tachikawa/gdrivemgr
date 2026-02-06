import unittest

from gdrivemgr.plan import Action


class TestAction(unittest.TestCase):
    def test_action_values(self) -> None:
        self.assertEqual(Action.CREATE_FOLDER.value, "CREATE_FOLDER")
        self.assertEqual(Action.DELETE_PERMANENT.value, "DELETE_PERMANENT")
        self.assertIn(Action.TRASH, Action)


if __name__ == "__main__":
    unittest.main()
