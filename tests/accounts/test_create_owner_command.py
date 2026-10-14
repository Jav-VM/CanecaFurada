import os
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.core.models import AuditEvent

from .factories import PASSWORD, make_user

CMD = "apps.accounts.management.commands.create_owner"


class CreateOwnerCommandTests(TestCase):
    def _run_interactive(self, answers, passwords):
        out = StringIO()
        with mock.patch("builtins.input", side_effect=answers), mock.patch(
            f"{CMD}.getpass", side_effect=passwords
        ):
            call_command("create_owner", stdout=out)
        return out.getvalue()

    def test_interactive_creates_first_owner(self):
        output = self._run_interactive(["Dueno@Example.com", "Dueño", "Ficticio"], [PASSWORD, PASSWORD])
        owner = User.objects.get()
        self.assertEqual(owner.role, User.Role.OWNER)
        self.assertEqual(owner.email, "dueno@example.com")
        self.assertNotIn(PASSWORD, output)
        event = AuditEvent.objects.get(action=AuditEvent.Action.OWNER_CREATED)
        self.assertIsNone(event.actor)

    def test_password_mismatch(self):
        with self.assertRaisesMessage(CommandError, "no coinciden"):
            self._run_interactive(["d@example.com", "D", "F"], [PASSWORD, PASSWORD + "x"])
        self.assertFalse(User.objects.exists())

    def test_weak_password_rejected(self):
        with self.assertRaises(CommandError):
            self._run_interactive(["d@example.com", "D", "F"], ["123", "123"])
        self.assertFalse(User.objects.exists())

    def test_refuses_when_owner_exists(self):
        make_user(email="dueno@example.com", role=User.Role.OWNER)
        with self.assertRaisesMessage(CommandError, "Ya existe un propietario"):
            self._run_interactive(["otro@example.com", "O", "F"], [PASSWORD, PASSWORD])
        self.assertEqual(User.objects.filter(role=User.Role.OWNER).count(), 1)

    def test_refuses_duplicate_email(self):
        make_user(email="dueno@example.com")
        with self.assertRaises(CommandError):
            self._run_interactive(["DUENO@example.com", "D", "F"], [PASSWORD, PASSWORD])
        self.assertFalse(User.objects.filter(role=User.Role.OWNER).exists())

    def test_noinput_reads_environment(self):
        env = {
            "CANECA_OWNER_EMAIL": "dueno@example.com",
            "CANECA_OWNER_FIRST_NAME": "Dueño",
            "CANECA_OWNER_LAST_NAME": "Ficticio",
            "CANECA_OWNER_PASSWORD": PASSWORD,
        }
        with mock.patch.dict(os.environ, env):
            call_command("create_owner", "--noinput", stdout=StringIO())
        self.assertTrue(User.objects.filter(email="dueno@example.com", role=User.Role.OWNER).exists())

    def test_noinput_missing_variables(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesMessage(CommandError, "CANECA_OWNER_PASSWORD"):
                call_command("create_owner", "--noinput", stdout=StringIO())
