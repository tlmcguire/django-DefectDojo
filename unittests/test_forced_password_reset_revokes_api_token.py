from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token

from dojo.models import User, UserContactInfo
from unittests.dojo_test_case import versioned_fixtures


@versioned_fixtures
class TestForcedPasswordResetRevokesApiToken(TestCase):

    """API tokens must not survive, or be issued during, a forced password reset."""

    fixtures = ["dojo_testdata.json"]

    def _make_user(self, username, *, forced):
        user = User.objects.create(username=username, email=f"{username}@dojo.com", is_active=True)
        user.set_password("OldPass123!@#")
        user.save()
        UserContactInfo.objects.update_or_create(user=user, defaults={"force_password_reset": forced})
        return user

    def _change_password(self, user):
        self.client.force_login(user)
        return self.client.post(
            reverse("change_password"),
            data={
                "current_password": "OldPass123!@#",
                "new_password": "NewPass123!@#",
                "confirm_password": "NewPass123!@#",
            },
        )

    def test_forced_reset_revokes_existing_token(self):
        user = self._make_user("forced-reset-token-user", forced=True)
        old_key = Token.objects.create(user=user).key

        resp = self._change_password(user)

        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Token.objects.filter(user=user).exists())
        # The pre-reset key no longer authenticates against the API (fresh client: no session).
        resp = Client().get("/api/v2/user_profile/", HTTP_AUTHORIZATION=f"Token {old_key}")
        self.assertIn(resp.status_code, {401, 403})

    def test_voluntary_change_keeps_token(self):
        user = self._make_user("voluntary-change-token-user", forced=False)
        token = Token.objects.create(user=user)

        resp = self._change_password(user)

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Token.objects.filter(key=token.key).exists())

    def test_token_endpoint_refuses_while_reset_pending(self):
        user = self._make_user("pending-reset-token-user", forced=True)

        resp = Client().post(reverse("api-token-auth"), {"username": user.username, "password": "OldPass123!@#"})

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Token.objects.filter(user=user).exists())

    def test_token_endpoint_issues_token_without_pending_reset(self):
        user = self._make_user("no-reset-token-user", forced=False)

        resp = Client().post(reverse("api-token-auth"), {"username": user.username, "password": "OldPass123!@#"})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["token"], Token.objects.get(user=user).key)
