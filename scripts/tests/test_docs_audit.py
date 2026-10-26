"""Focused checks for document moves, duplicate headings and index coverage."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import docs_audit


class DocsAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.root_patch = patch.object(docs_audit, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_same_file_missing_anchor_is_reported(self):
        path = self.write("README.md", "# 标题\n\n[正确](#标题) [失效](#不存在)\n")
        issues = docs_audit.check_links([path])
        self.assertEqual(len(issues), 1)
        self.assertIn("broken local anchor -> #不存在", issues[0])

    def test_existing_file_does_not_hide_a_missing_chapter(self):
        source = self.write("README.md", "[章节](docs/target.md#removed)\n")
        self.write("docs/target.md", "# 保留\n")
        self.assertIn("broken local anchor", docs_audit.check_links([source])[0])

    def test_duplicates_reserve_already_used_suffixes(self):
        path = self.write("README.md", "# Same\n## Same\n## Same-1\n## Same\n")
        self.assertEqual(docs_audit.heading_anchors(path), {"same", "same-1", "same-1-1", "same-2"})

    def test_encoded_chinese_file_and_fragment(self):
        source = self.write("README.md", "[章节](docs/%E4%B8%AD%E6%96%87.md#%E7%AB%A0%E8%8A%82)\n")
        self.write("docs/中文.md", "# 章节\n")
        self.assertEqual(docs_audit.check_links([source]), [])

    def test_fences_ignore_links_and_headings_until_matching_close(self):
        path = self.write(
            "README.md",
            "# Real\n\n````md\n```\n# Example\n[bad](missing.md)\n````\n"
            "~~~md\n# Other example\n[bad](missing.md)\n~~~\n\n[good](#real)\n",
        )
        self.assertEqual(docs_audit.heading_anchors(path), {"real"})
        self.assertEqual(docs_audit.check_links([path]), [])

    def test_explicit_anchors_setext_and_inline_heading_markup(self):
        path = self.write(
            "README.md",
            '<a id="stable"></a>\n\nSetext\n======\n\n## [Link](target.md) 与 `code` **文字**\n',
        )
        self.assertEqual(
            docs_audit.heading_anchors(path), {"stable", "setext", "link-与-code-文字"}
        )

    def test_file_without_fragment_and_external_links_remain_valid(self):
        source = self.write(
            "README.md", "[本地](docs/target.md) [外部](https://example.com/#anything)\n"
        )
        self.write("docs/target.md", "正文，没有标题。\n")
        self.assertEqual(docs_audit.check_links([source]), [])

    def test_index_can_reach_nested_files_and_reports_orphans(self):
        index = self.write("docs/archive/README.md", "[阶段](stage/README.md)\n")
        nested = self.write("docs/archive/stage/README.md", "[记录](record.md)\n")
        record = self.write("docs/archive/stage/record.md", "# 记录\n")
        orphan = self.write("docs/archive/orphan.md", "# 漏列\n")
        self.assertEqual(docs_audit.check_index_coverage([index, nested, record]), [])
        issues = docs_audit.check_index_coverage([index, nested, record, orphan])
        self.assertEqual(len(issues), 1)
        self.assertIn("docs/archive/orphan.md: missing from", issues[0])


if __name__ == "__main__":
    unittest.main()
