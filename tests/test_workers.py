import shutil
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from tglol.config import Config
from tglol.db import (
    add_account,
    claim_accounts_for_worker,
    delete_worker,
    get_account,
    get_worker,
    init_db,
    list_worker_stats,
    list_workers,
    reset_worker_limits,
    save_worker,
    set_worker_limit,
    update_worker_identity,
)
from tglol.keyboards import workers_list_menu


class WorkerQuotaTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.config = Config(
            bot_token="token",
            admin_ids=frozenset({1}),
            telegram_api_id=123,
            telegram_api_hash="hash",
            bot_parse_mode="HTML",
            data_dir=self.tmpdir,
            sessions_dir=self.tmpdir / "sessions",
            json_dir=self.tmpdir / "json",
            temp_dir=self.tmpdir / "tmp",
            db_path=self.tmpdir / "bot.sqlite3",
            default_lang_code="en",
            default_system_lang_code="en-US",
            default_lang_pack="tdesktop",
            trigger_chat_id=-100123,
        )
        init_db(self.config)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def add_account(self, phone: str) -> int:
        return add_account(
            self.config,
            {
                "phone": phone,
                "telegram_user_id": None,
                "username": None,
                "first_name": None,
                "last_name": None,
                "session_path": str(self.tmpdir / f"{phone}.session"),
                "json_original_path": None,
                "json_effective_path": None,
                "json_source": "generated",
                "twofa_password": None,
                "source_type": "test",
                "status": "active",
                "created_by": 1,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
        )

    def test_worker_crud_and_name_fields(self):
        save_worker(
            self.config,
            user_id=42,
            first_name="Ivan",
            last_name="Petrov",
            username="ivan",
            remaining_limit=5,
            created_by=1,
        )
        worker = get_worker(self.config, 42)
        self.assertEqual((worker.first_name, worker.last_name, worker.remaining_limit), ("Ivan", "Petrov", 5))
        self.assertEqual([item.user_id for item in list_workers(self.config)], [42])
        self.assertTrue(set_worker_limit(self.config, 42, 3))
        self.assertEqual(get_worker(self.config, 42).remaining_limit, 3)
        self.assertTrue(
            update_worker_identity(
                self.config,
                42,
                first_name="Petr",
                last_name=None,
                username="petr",
            )
        )
        self.assertEqual(get_worker(self.config, 42).first_name, "Petr")
        self.assertTrue(delete_worker(self.config, 42))
        self.assertIsNone(get_worker(self.config, 42))

    def test_claim_respects_and_consumes_remaining_limit(self):
        first_id = self.add_account("10001")
        second_id = self.add_account("10002")
        save_worker(
            self.config,
            user_id=42,
            first_name="Ivan",
            last_name=None,
            username=None,
            remaining_limit=1,
            created_by=1,
        )

        claimed = claim_accounts_for_worker(self.config, [first_id, second_id], worker_id=42)
        self.assertEqual([account.id for account in claimed], [first_id])
        self.assertEqual(get_worker(self.config, 42).remaining_limit, 0)
        self.assertEqual(get_account(self.config, first_id).account_stage, "issued")
        self.assertNotEqual(get_account(self.config, second_id).account_stage, "issued")
        self.assertEqual(claim_accounts_for_worker(self.config, [second_id], worker_id=42), [])

    def test_unknown_worker_cannot_claim(self):
        account_id = self.add_account("10003")
        self.assertEqual(claim_accounts_for_worker(self.config, [account_id], worker_id=999), [])
        self.assertNotEqual(get_account(self.config, account_id).account_stage, "issued")

    def test_stats_and_reset_start_a_new_period(self):
        first_id = self.add_account("20001")
        second_id = self.add_account("20002")
        save_worker(
            self.config,
            user_id=77,
            first_name="Anna",
            last_name="Test",
            username="anna",
            remaining_limit=3,
            created_by=1,
        )
        claimed = claim_accounts_for_worker(
            self.config,
            [first_id, second_id],
            worker_id=77,
            requested_count=5,
        )
        self.assertEqual(len(claimed), 2)

        stats = list_worker_stats(self.config)[0]
        self.assertEqual(stats.trigger_count, 1)
        self.assertEqual(stats.requested_count, 5)
        self.assertEqual(stats.issued_count, 2)
        self.assertEqual(stats.phones, ("20001", "20002"))
        self.assertEqual(stats.worker.remaining_limit, 1)
        self.assertEqual(stats.worker.configured_limit, 3)

        reset = reset_worker_limits(self.config)[0]
        self.assertEqual(reset.previous_remaining, 1)
        self.assertEqual(reset.restored_count, 2)
        self.assertEqual(reset.requested_count, 5)
        self.assertEqual(get_worker(self.config, 77).remaining_limit, 3)

        fresh_stats = list_worker_stats(self.config)[0]
        self.assertEqual(fresh_stats.trigger_count, 0)
        self.assertEqual(fresh_stats.requested_count, 0)
        self.assertEqual(fresh_stats.issued_count, 0)
        self.assertEqual(fresh_stats.phones, ())

    def test_worker_list_is_paginated(self):
        workers = [
            SimpleNamespace(user_id=index, first_name=f"Worker {index}", last_name=None)
            for index in range(1, 22)
        ]
        first_page = workers_list_menu(workers, page=0)
        second_page = workers_list_menu(workers, page=1)
        first_callbacks = [button.callback_data for row in first_page.inline_keyboard for button in row]
        second_callbacks = [button.callback_data for row in second_page.inline_keyboard for button in row]
        self.assertIn("workers:list_page:1", first_callbacks)
        self.assertIn("workers:list_page:0", second_callbacks)
        self.assertIn("workers:open:21", second_callbacks)

    def test_existing_worker_table_is_migrated(self):
        legacy_path = self.tmpdir / "legacy.sqlite3"
        with sqlite3.connect(legacy_path) as connection:
            connection.execute(
                """
                CREATE TABLE workers (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT,
                    username TEXT,
                    remaining_limit INTEGER NOT NULL,
                    created_by INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO workers VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (88, "Legacy", None, None, 7, 1, "now", "now"),
            )
        legacy_config = replace(self.config, db_path=legacy_path)
        init_db(legacy_config)
        worker = get_worker(legacy_config, 88)
        self.assertEqual(worker.remaining_limit, 7)
        self.assertEqual(worker.configured_limit, 7)


if __name__ == "__main__":
    unittest.main()
