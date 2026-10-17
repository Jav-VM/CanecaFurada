"""Fase 16: provincia y localidad por código postal, endpoint de localidades y campo sexo."""
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts import postal, services
from apps.accounts.models import CustomerProfile

from .factories import registration_data


class PostalModuleTests(TestCase):
    def test_province_from_prefix(self):
        for code, province in (("15001", "A Coruña"), ("27001", "Lugo"), ("01001", "Araba/Álava"), ("52001", "Melilla")):
            with self.subTest(code=code):
                self.assertEqual(postal.province_for("ES", code), province)
        self.assertEqual(postal.province_for("PT", "4000-123"), "")
        self.assertEqual(postal.province_for("ES", ""), "")

    def test_all_52_provinces(self):
        self.assertEqual(sorted(postal.PROVINCES_ES), [f"{n:02d}" for n in range(1, 53)])

    def test_localities(self):
        self.assertEqual(postal.localities_for("ES", "15142"), ["Arteixo"])
        self.assertEqual(postal.localities_for("ES", "22583"), ["Areny de Noguera / Arén", "Tremp"])
        self.assertEqual(postal.localities_for("ES", "04070"), [])
        self.assertEqual(postal.localities_for("PT", "4000-123"), [])

    def test_canonical_locality(self):
        self.assertEqual(postal.canonical_locality("ES", "15179", "  oleiros "), "Oleiros")
        self.assertEqual(postal.canonical_locality("ES", "04070", " Mi  pueblo "), "Mi pueblo")
        self.assertEqual(postal.canonical_locality("ES", "04070", ""), "")
        for value, code in (("", "locality_required"), ("Lugo", "invalid_locality")):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as ctx:
                    postal.canonical_locality("ES", "15179", value)
                self.assertEqual(ctx.exception.code, code)

    def test_returned_list_is_a_copy(self):
        postal.localities_for("ES", "15142").append("Inventada")
        self.assertEqual(postal.localities_for("ES", "15142"), ["Arteixo"])


class LocalitiesViewTests(TestCase):
    url = reverse("accounts:localities")

    def setUp(self):
        cache.clear()

    def test_returns_localities_and_is_cacheable(self):
        response = self.client.get(self.url, {"cp": " 15179 "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"localities": ["Oleiros"]})
        self.assertIn("max-age=86400", response["Cache-Control"])

    def test_postal_code_without_data(self):
        self.assertEqual(self.client.get(self.url, {"cp": "04070"}).json(), {"localities": []})

    def test_invalid_postal_code_is_400_without_echo(self):
        for value in ("99999", "<script>", "", "1" * 50):
            with self.subTest(value=value):
                response = self.client.get(self.url, {"cp": value})
                self.assertEqual(response.status_code, 400)
                if value:
                    self.assertNotIn(value, response.content.decode())

    def test_only_get(self):
        self.assertEqual(self.client.post(self.url, {"cp": "15001"}).status_code, 405)

    @override_settings(POSTAL_LOOKUP_MAX_PER_IP_PER_HOUR=2)
    def test_rate_limited_per_ip(self):
        for _unused in range(2):
            self.assertEqual(self.client.get(self.url, {"cp": "15001"}).status_code, 200)
        self.assertEqual(self.client.get(self.url, {"cp": "15001"}).status_code, 429)


class SexFieldTests(TestCase):
    def test_database_rejects_unknown_values(self):
        user = services.register_customer(**registration_data())
        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomerProfile.objects.filter(user=user).update(sex="OTRO")

    def test_profile_without_sex_is_complete(self):
        # Fase 25: el sexo es opcional (minimización de datos).
        user = services.register_customer(**registration_data())
        CustomerProfile.objects.filter(user=user).update(sex="")
        self.assertEqual(CustomerProfile.objects.get(user=user).missing_required_fields(), [])
