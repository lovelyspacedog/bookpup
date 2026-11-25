import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.jobs as jobs
import lib.library as library
import lib.transfer as transfer
import lib.user_paths as user_paths
from lib.safe_ids import validate_path_segment, validate_username
from lib.staging import create_staging, staging_dir, _safe_extract_zip
from lib.url_safety import assert_fetchable_https_url
from lib.import_session import create_session, finish_session, write_chunk
import lib.auth as auth


class AuditFixesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.STAGING_DIR = core.CONFIG_DIR / "staging"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            json.dumps({"username": "alice", "password": "pw", "port": 18478})
        )
        accounts.reload_accounts()
        accounts.create_user("bob", "pw2")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None

    def test_reject_dotdot_username(self) -> None:
        with self.assertRaises(ValueError):
            validate_username("..")

    def test_reject_dotdot_staging(self) -> None:
        with self.assertRaises(ValueError):
            staging_dir("..")

    def test_staging_cross_user_denied(self) -> None:
        job = jobs.create_job("download", owner="alice", title="book")
        sid = job["id"]
        create_staging(sid)
        (core.STAGING_DIR / sid / "raw.epub").write_bytes(b"data")
        jobs.save_job({**job, "staging_id": sid, "state": "done"})
        with self.assertRaises(PermissionError):
            transfer.assert_staging_access(sid, "bob", False)

    def test_cover_quota(self) -> None:
        user_paths.set_user("alice")
        accounts.update_user("alice", {"quota_bytes": 100})
        library.add_bytes("small", b"x" * 40, "txt", source="download")
        item_id = library.list_items()[0]["id"]
        with self.assertRaises(ValueError):
            library.set_cover(item_id, b"\xff\xd8\xff" + b"x" * 80)

    def test_zip_slip_blocked(self) -> None:
        import io

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../evil.txt", b"owned")
        buf.seek(0)
        with zipfile.ZipFile(buf) as zf:
            dest = Path(self.tmp.name) / "out"
            with self.assertRaises(ValueError):
                _safe_extract_zip(zf, dest)

    def test_cover_url_blocks_loopback(self) -> None:
        with self.assertRaises(ValueError):
            assert_fetchable_https_url("https://127.0.0.1/cover.jpg")

    def test_import_session_owner(self) -> None:
        user_paths.set_user("alice")
        sess = create_session([{"name": "part-0001.calibre-data", "size": 4}])
        sid = sess["session_id"]
        user_paths.set_user("bob")
        with self.assertRaises(PermissionError):
            write_chunk(sid, "part-0001.calibre-data", 0, b"test")

    def test_complete_job_respects_cancel(self) -> None:
        job = jobs.create_job("download", owner="alice")
        jobs.cancel_job(job["id"])
        self.assertIsNone(jobs.complete_job_success(job["id"]))

    def test_fresh_upload_session(self) -> None:
        user_paths.set_user("alice")
        sess = create_session([{"name": "trail.txt", "size": 11}], kind="fresh_upload")
        sid = sess["session_id"]
        write_chunk(sid, "trail.txt", 0, b"hello trail")
        out = finish_session(sid)
        self.assertTrue(out.get("item", {}).get("id"))
        self.assertEqual(out["item"]["format"], "txt")

    def test_import_session_rejects_over_quota(self) -> None:
        user_paths.set_user("alice")
        accounts.update_user("alice", {"quota_bytes": 50})
        with self.assertRaises(ValueError):
            create_session([{"name": "big.bin", "size": 100}], kind="fresh_upload")

    def test_disabled_user_revokes_session(self) -> None:
        token = auth.create_token("bob")
        self.assertEqual(auth.session_user(f"Bearer {token}"), "bob")
        accounts.update_user("bob", {"enabled": False})
        self.assertIsNone(auth.session_user(f"Bearer {token}"))


if __name__ == "__main__":
    unittest.main()