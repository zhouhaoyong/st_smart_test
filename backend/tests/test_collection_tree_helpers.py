import unittest
from types import SimpleNamespace

from services.collection_tree import build_collection_tree


class CollectionTreeHelperTests(unittest.TestCase):
    def test_build_collection_tree_uses_recursive_interface_counts(self):
        collections = [
            SimpleNamespace(id=1, name="根目录", description=None, project_id=10, parent_id=None),
            SimpleNamespace(id=2, name="用户", description=None, project_id=10, parent_id=1),
            SimpleNamespace(id=3, name="账单", description=None, project_id=10, parent_id=2),
        ]

        tree = build_collection_tree(collections, {3: 6})

        self.assertEqual(tree[0]["interface_count"], 6)
        self.assertEqual(tree[0]["children"][0]["interface_count"], 6)
        self.assertEqual(tree[0]["children"][0]["children"][0]["interface_count"], 6)

    def test_build_collection_tree_rolls_up_interface_status_summary(self):
        collections = [
            SimpleNamespace(id=1, name="根目录", description=None, project_id=10, parent_id=None),
            SimpleNamespace(id=2, name="用户", description=None, project_id=10, parent_id=1),
        ]

        tree = build_collection_tree(collections, {
            1: {"total_count": 2, "pending_count": 1, "done_count": 1},
            2: {"total_count": 3, "pending_count": 0, "done_count": 3},
        })

        root = tree[0]
        child = root["children"][0]
        self.assertEqual(root["interface_count"], 5)
        self.assertEqual(root["pending_interface_count"], 1)
        self.assertEqual(root["done_interface_count"], 4)
        self.assertEqual(root["interface_status"], "pending")
        self.assertEqual(child["interface_status"], "done")

    def test_empty_collection_status_is_neutral(self):
        collections = [
            SimpleNamespace(id=1, name="空目录", description=None, project_id=10, parent_id=None),
        ]

        tree = build_collection_tree(collections, {})

        self.assertEqual(tree[0]["interface_count"], 0)
        self.assertEqual(tree[0]["interface_status"], "empty")

if __name__ == "__main__":
    unittest.main()
