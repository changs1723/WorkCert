"""CLI regressions for immutable verification, including failing audits."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).with_name("reproduce_v03.py")


class ReproductionContract(unittest.TestCase):
    def invoke(self, source, output, *args):
        return subprocess.run([sys.executable, str(RUNNER), "--verify-only", "--checks", "integrity",
                               "--source-root", str(source), "--output-dir", str(output), *args],
                              capture_output=True, text=True)

    def fixture(self, base):
        source = base / "frozen"
        assert source.resolve().parent == base.resolve()
        source.mkdir()
        inputs = {"data/prepared/source.csv": b"x,f\n0,0\n1,1\n",
                  "validation/results/saved.json": b'{"work": 0.5}\n',
                  "article/main.tex": b"Frozen article text\n",
                  "article_inputs/metrics.json": b'{"version": "0.3.0"}\n',
                  "figures/fig01.pdf": b"Frozen figure fixture\n"}
        for name, blob in inputs.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
        (source / "MANIFEST.sha256").write_text("".join(hashlib.sha256(blob).hexdigest() + "  " + name + "\n"
                                                       for name, blob in inputs.items()), encoding="utf8")
        return source

    def fingerprint(self, root):
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob("*") if p.is_file()}

    def test_success_preserves_every_source_byte(self):
        with tempfile.TemporaryDirectory(prefix="workcert-readonly-test-") as folder:
            base = Path(folder).resolve()
            source = self.fixture(base)
            before = self.fingerprint(source)
            result = self.invoke(source, base / "report")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, self.fingerprint(source))
            report = json.loads((base / "report/verification_summary.json").read_text())
            self.assertEqual(report["status"], "PASS")
            self.assertTrue(report["source_unchanged"])
            self.assertEqual(report["changed_source_files"], [])

    def test_corrupt_source_and_saved_result_are_rejected_without_repair(self):
        for name in ("data/prepared/source.csv", "validation/results/saved.json"):
            with self.subTest(file=name), tempfile.TemporaryDirectory(prefix="workcert-readonly-test-") as folder:
                base = Path(folder).resolve()
                source = self.fixture(base)
                (source / name).write_bytes((source / name).read_bytes() + b"tampered")
                before = self.fingerprint(source)
                result = self.invoke(source, base / "report")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(before, self.fingerprint(source))
                report = json.loads((base / "report/verification_summary.json").read_text())
                self.assertEqual(report["status"], "FAIL")
                self.assertIn(name, report["error"])
                self.assertTrue(report["source_unchanged"])

    def test_output_in_frozen_tree_and_generation_flags_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="workcert-readonly-test-") as folder:
            base = Path(folder).resolve()
            source = self.fixture(base)
            before = self.fingerprint(source)
            forbidden = [(source / name / "report", ())
                         for name in ("data", "article", "article_inputs", "figures")]
            forbidden.append((base / "report", ("--figures",)))
            for output, args in forbidden:
                result = self.invoke(source, output, *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(output.exists())
            self.assertEqual(before, self.fingerprint(source))

    def test_existing_report_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="workcert-readonly-test-") as folder:
            base = Path(folder).resolve()
            source = self.fixture(base)
            report = base / "report"
            report.mkdir()
            (report / "keep.txt").write_text("previous audit")
            result = self.invoke(source, report)
            self.assertEqual(result.returncode, 2)
            self.assertEqual((report / "keep.txt").read_text(), "previous audit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
