from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.views import View

from apps.accounts.models import User
from apps.accounts.permissions import (
    RoleRequiredMixin,
    has_role,
    is_owner,
    is_staff_member,
    role_required,
)

from .factories import make_user


@role_required(User.Role.OWNER, User.Role.EMPLOYEE)
def staff_view(request):
    return HttpResponse("ok")


class OwnerOnlyView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.OWNER,)

    def get(self, request):
        return HttpResponse("ok")


class PermissionHelpersTests(TestCase):
    def setUp(self):
        self.owner = make_user(email="o@example.com", role=User.Role.OWNER)
        self.employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        self.customer = make_user(email="c@example.com")

    def test_helpers(self):
        self.assertTrue(is_owner(self.owner))
        self.assertFalse(is_owner(self.employee))
        self.assertTrue(is_staff_member(self.employee))
        self.assertFalse(is_staff_member(self.customer))
        self.assertFalse(has_role(AnonymousUser(), User.Role.CUSTOMER))
        self.assertFalse(has_role(None, User.Role.CUSTOMER))

    def test_inactive_user_has_no_role(self):
        self.owner.is_active = False
        self.assertFalse(is_owner(self.owner))


class RoleRequiredTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner = make_user(email="o@example.com", role=User.Role.OWNER)
        self.employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        self.customer = make_user(email="c@example.com")

    def _request(self, user):
        request = self.factory.get("/zona-privada/")
        request.user = user
        return request

    def test_decorator_redirects_anonymous_to_login(self):
        response = staff_view(self._request(AnonymousUser()))
        self.assertEqual(response.status_code, 302)
        self.assertIn("next=/zona-privada/", response["Location"])

    def test_decorator_denies_customer(self):
        with self.assertRaises(PermissionDenied):
            staff_view(self._request(self.customer))

    def test_decorator_allows_staff(self):
        for user in (self.owner, self.employee):
            with self.subTest(role=user.role):
                self.assertEqual(staff_view(self._request(user)).status_code, 200)

    def test_mixin(self):
        view = OwnerOnlyView.as_view()
        self.assertEqual(view(self._request(AnonymousUser())).status_code, 302)
        for user in (self.employee, self.customer):
            with self.subTest(role=user.role), self.assertRaises(PermissionDenied):
                view(self._request(user))
        self.assertEqual(view(self._request(self.owner)).status_code, 200)
