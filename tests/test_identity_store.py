import os
import sqlite3
import tempfile
import unittest

from modules.security.identity_store import IdentityStore


class IdentityStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "identity.sqlite3")
        self.store = IdentityStore(self.database_path)
        self.store.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _user(self, email):
        return self.store.create_user(email, "correct-horse-battery-42")

    def test_create_organization_user_and_membership(self):
        organization = self.store.create_organization("Northwind Operations")
        user = self._user("Owner@Example.com")
        membership = self.store.add_membership(organization["id"], user["id"], "owner")

        self.assertEqual(membership["role"], "owner")
        self.assertEqual(membership["organization_name"], "Northwind Operations")
        self.assertEqual(user["email"], "owner@example.com")

    def test_password_is_hashed_and_authentication_is_case_insensitive(self):
        user = self._user("owner@example.com")
        connection = sqlite3.connect(self.database_path)
        try:
            stored_hash = connection.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertNotEqual(stored_hash, "correct-horse-battery-42")
        self.assertTrue(stored_hash.startswith("scrypt:"))
        self.assertEqual(
            self.store.authenticate("OWNER@example.com", "correct-horse-battery-42")["id"],
            user["id"],
        )
        self.assertIsNone(self.store.authenticate("owner@example.com", "wrong-password"))

    def test_duplicate_email_is_rejected_after_normalization(self):
        self._user("owner@example.com")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self._user(" Owner@Example.com ")

    def test_short_password_and_invalid_email_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "12 characters"):
            self.store.create_user("owner@example.com", "short")
        with self.assertRaisesRegex(ValueError, "valid email"):
            self.store.create_user("not-an-email", "correct-horse-battery-42")

    def test_membership_is_organization_scoped(self):
        org_a = self.store.create_organization("Organization A")
        org_b = self.store.create_organization("Organization B")
        user_a = self._user("a@example.com")
        user_b = self._user("b@example.com")
        self.store.add_membership(org_a["id"], user_a["id"], "owner")
        self.store.add_membership(org_b["id"], user_b["id"], "viewer")

        self.assertIsNone(self.store.get_membership(org_b["id"], user_a["id"]))
        self.assertEqual(
            self.store.list_active_memberships(user_a["id"]),
            [{
                "organization_id": org_a["id"],
                "role": "owner",
                "organization_name": "Organization A",
            }],
        )

    def test_invalid_role_and_duplicate_membership_are_rejected(self):
        organization = self.store.create_organization("Northwind")
        user = self._user("owner@example.com")
        with self.assertRaisesRegex(ValueError, "valid organization role"):
            self.store.add_membership(organization["id"], user["id"], "superadmin")
        self.store.add_membership(organization["id"], user["id"], "owner")
        with self.assertRaisesRegex(ValueError, "already has a membership"):
            self.store.add_membership(organization["id"], user["id"], "admin")

    def test_disabled_user_cannot_authenticate(self):
        user = self._user("owner@example.com")
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (user["id"],))
            connection.commit()
        finally:
            connection.close()
        self.assertIsNone(self.store.authenticate("owner@example.com", "correct-horse-battery-42"))


if __name__ == "__main__":
    unittest.main()
