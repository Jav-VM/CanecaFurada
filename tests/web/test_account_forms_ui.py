"""Presentación de los formularios de cuenta en el sistema de diseño (Fase 3)."""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from tests.accounts.factories import make_user, registration_post_data


class RegisterFormUITests(TestCase):
    url = reverse("accounts:register")

    def setUp(self):
        cache.clear()

    def test_sections_are_numbered_fieldsets_in_order(self):
        html = self.client.get(self.url).content.decode()
        titles = ["Datos personales", "Dónde vives", "Acceso a la cuenta", "Preferencias de comunicación"]
        positions = [html.index(f"Paso {n}: </span>{title}") for n, title in enumerate(titles, start=1)]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(html.count('<fieldset class="form-section">'), 4)

    def test_required_and_optional_fields_are_marked(self):
        response = self.client.get(self.url)
        self.assertContains(response, "son obligatorios")
        self.assertContains(response, "El teléfono móvil es opcional")
        html = response.content.decode()
        phone_label = html[html.index('for="id_phone_number"') : html.index('id="id_phone_number"')]
        self.assertIn("(opcional)", phone_label)
        email_label = html[html.index('for="id_email"') : html.index('id="id_email"')]
        self.assertIn("(obligatorio)", email_label)

    def test_form_has_loading_state_and_csrf(self):
        response = self.client.get(self.url)
        self.assertContains(response, "data-loading")
        self.assertContains(response, 'data-loading-text="Creando cuenta…"')
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_errors_are_accessible_and_safe_data_is_kept(self):
        data = registration_post_data(last_name="", postal_code="99999")
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        # Resumen de errores enfocable y anunciado.
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, "data-error-summary")
        self.assertContains(response, 'href="#id_last_name"')
        # Cada campo con error queda marcado y enlazado con su mensaje.
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'id="id_last_name_error"')
        self.assertContains(response, 'aria-describedby="id_last_name_error"')
        # Los datos no sensibles se conservan.
        self.assertContains(response, 'value="Lúa"')
        self.assertContains(response, 'value="A Coruña"')
        self.assertContains(response, 'value="nueva@example.com"')

    def test_sex_group_is_a_fieldset_linked_to_its_error(self):
        # Fase 25: el sexo es opcional; un valor no válido sigue enlazando su error al grupo.
        response = self.client.post(self.url, registration_post_data(sex="OTRO"))
        self.assertContains(response, '<fieldset class="field field-choices" aria-describedby="id_sex_error">')
        self.assertContains(response, 'id="id_sex_error"', count=1)

    def test_passwords_are_never_refilled(self):
        data = registration_post_data(last_name="")
        response = self.client.post(self.url, data)
        self.assertNotContains(response, data["password1"])
        html = response.content.decode()
        for name in ("password1", "password2"):
            tag = html[html.index(f'name="{name}"') - 30 : html.index(f'name="{name}"') + 200]
            self.assertNotIn("value=", tag.split(">")[0])


class RegisterDoneUITests(TestCase):
    def test_confirmation_says_verification_is_pending(self):
        response = self.client.get(reverse("accounts:register_done"))
        self.assertContains(response, "Falta un paso: verificar tu email")
        self.assertContains(response, "pendiente de verificación")
        self.assertContains(response, reverse("accounts:resend_verification"))
        content = response.content.decode().lower()
        for misleading in ("cuenta activada", "cuenta activa", "ya está activa", "completamente"):
            with self.subTest(misleading):
                self.assertNotIn(misleading, content)


class AccountPagesUITests(TestCase):
    def setUp(self):
        cache.clear()

    def test_account_pages_render_in_design_system(self):
        for url_name in ("accounts:login", "accounts:register", "accounts:resend_verification", "accounts:password_reset"):
            with self.subTest(url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "accounts/_layout.html")
                self.assertContains(response, "css/app.css")

    def test_verify_email_pages_render(self):
        response = self.client.get(reverse("accounts:verify_email", args=["token-ficticio"]))
        self.assertTemplateUsed(response, "accounts/verify_email_confirm.html")
        self.assertContains(response, "Confirmar email")
        response = self.client.post(reverse("accounts:verify_email", args=["token-ficticio"]))
        self.assertTemplateUsed(response, "accounts/verify_email_result.html")
        self.assertContains(response, "No se ha podido confirmar el email")
        self.assertNotContains(response, "token-ficticio")

    def test_login_error_keeps_email_but_not_password(self):
        make_user("cliente@example.com")
        response = self.client.post(
            reverse("accounts:login"), {"username": "cliente@example.com", "password": "incorrecta-123"}
        )
        self.assertContains(response, "data-error-summary")
        self.assertContains(response, "Email o contraseña incorrectos.")
        self.assertContains(response, 'value="cliente@example.com"')
        self.assertNotContains(response, "incorrecta-123")

    def test_unverified_profile_shows_pending_notice(self):
        user = make_user("cliente@example.com")
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "Tu email está pendiente de verificación.")
        self.assertContains(response, "Pendiente de verificación")
        self.assertNotContains(response, ">Verificado<")

    def test_verified_profile_shows_verified_badge(self):
        from django.utils import timezone

        user = make_user("cliente@example.com", email_verified_at=timezone.now())
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, ">Verificado<")
        self.assertNotContains(response, "Tu email está pendiente de verificación.")
