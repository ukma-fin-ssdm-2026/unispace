"""CI scope regression tests, prepared with Claude."""

import unittest

from scripts.ci_change_scope import requires_full_ci


class ChangeScopeTests(unittest.TestCase):
    def test_documentation_only_skips_heavy_jobs(self):
        self.assertFalse(requires_full_ci(["TeamCharter.md", "docs/ci-cd/dora-summary.md"]))

    def test_video_link_skips_heavy_jobs(self):
        self.assertFalse(requires_full_ci(["Labs/Lab10/video_Spirina.txt"]))

    def test_code_tests_and_config_require_full_ci(self):
        for path in ["Backend/api/views.py", "Backend/api/tests/test_api.py", ".github/workflows/ci.yml"]:
            with self.subTest(path=path):
                self.assertTrue(requires_full_ci([path]))

    def test_frontend_requires_full_ci(self):
        self.assertTrue(requires_full_ci(["Frontend/static/js/api.js"]))

    def test_generated_schema_requires_full_ci(self):
        self.assertTrue(requires_full_ci(["docs/api/openapi-generated.yaml"]))

    def test_mixed_changes_require_full_ci(self):
        self.assertTrue(requires_full_ci(["README.md", "Backend/api/views.py"]))

    def test_unknown_file_requires_full_ci(self):
        self.assertTrue(requires_full_ci(["new-config.yml"]))

    def test_empty_diff_requires_full_ci(self):
        self.assertTrue(requires_full_ci([]))

    def test_renamed_source_deleted_path_requires_full_ci(self):
        self.assertTrue(requires_full_ci(["Backend/old.py", "docs/old.py"]))


if __name__ == "__main__":
    unittest.main()
