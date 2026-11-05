import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('progress_builder', ROOT / 'scripts/build_progress_page.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class ProgressPageTests(unittest.TestCase):
    def test_current_task_table(self):
        source = (ROOT / 'docs/任务协调.md').read_text()
        tasks = builder.parse_tasks(source)
        self.assertEqual(len(tasks), 9)
        self.assertTrue(any(t['title'] == '完整动作过程接入' for t in tasks))
        self.assertEqual(len({task['id'] for task in tasks}), len(tasks))
        for task in tasks:
            self.assertIn(task['category'], {'pending', 'review', 'delivered'})
            self.assertTrue(task['status'] and task['evidence'] and task['owner'])

    def test_status_categories_are_independent_of_live_progress(self):
        source = '| 工作项 | 状态 | 证据 | 责任方 |\n|---|---|---|---|\n| a | 未实现 | e | o |\n| b | 本阶段已交付 | e | o |\n| c | 待验收 | e | o |\n### end'
        self.assertEqual([task['category'] for task in builder.parse_tasks(source)], ['pending', 'delivered', 'review'])

    def test_ids_stable_after_status_edit(self):
        source = (ROOT / 'docs/任务协调.md').read_text()
        changed = source.replace('本阶段已交付', '待开展')
        self.assertEqual([t['id'] for t in builder.parse_tasks(source)], [t['id'] for t in builder.parse_tasks(changed)])

    def test_documents_exist(self):
        for _, path in builder.DOCUMENTS.values():
            self.assertTrue((ROOT / path).is_file())

    def test_missing_table_fails(self):
        with self.assertRaises(IndexError):
            builder.parse_tasks('No task table')


if __name__ == '__main__':
    unittest.main()
