import datetime

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.accounts import birthdays, validators
from apps.accounts.models import CustomerProfile

from .factories import make_user

TODAY = datetime.date(2026, 10, 14)


class PhoneValidationTests(SimpleTestCase):
    def test_normalizes_spanish_mobile(self):
        for value in ("600000001", "600 00 00 01", "+34 600-000-001", "0034600000001"):
            with self.subTest(value=value):
                self.assertEqual(validators.normalize_phone_number(value), "+34600000001")

    def test_empty_is_allowed(self):
        self.assertEqual(validators.normalize_phone_number("  "), "")
        self.assertEqual(validators.normalize_phone_number(None), "")

    def test_rejects_invalid_and_non_mobile(self):
        for value in ("12", "6000000011111", "letras", "+34 981 000 000"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validators.normalize_phone_number(value)

    def test_model_validator_requires_e164(self):
        validators.validate_e164("+34600000001")
        with self.assertRaises(ValidationError):
            validators.validate_e164("600000001")


class PostalCodeTests(SimpleTestCase):
    def test_spanish_codes(self):
        validators.validate_postal_code("15001", "ES")
        validators.validate_postal_code("52001", "ES")
        for value in ("00001", "53001", "1500", "150011"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validators.validate_postal_code(value, "ES")

    def test_generic_codes(self):
        validators.validate_postal_code("75001", "FR")
        validators.validate_postal_code("SW1A 1AA", "GB")
        with self.assertRaises(ValidationError):
            validators.validate_postal_code("<script>", "FR")


@override_settings(ACCOUNTS_MIN_CUSTOMER_AGE=18)
class DateOfBirthTests(SimpleTestCase):
    def test_limits(self):
        validators.validate_date_of_birth(datetime.date(2008, 10, 14), today=TODAY)  # 18 hoy
        for value in (
            datetime.date(2008, 10, 15),  # 17
            datetime.date(2026, 10, 15),  # futura
            datetime.date(1900, 1, 1),  # más de 120 años
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validators.validate_date_of_birth(value, today=TODAY)

    def test_rejects_non_dates(self):
        for value in ("2000-01-01", None, datetime.datetime(2000, 1, 1)):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validators.validate_date_of_birth(value, today=TODAY)

    def test_leap_day_age(self):
        born = datetime.date(2004, 2, 29)
        self.assertEqual(validators.age_on(born, datetime.date(2022, 2, 28)), 17)
        self.assertEqual(validators.age_on(born, datetime.date(2022, 3, 1)), 18)
        self.assertEqual(validators.age_on(born, datetime.date(2024, 2, 29)), 20)


class BirthdayTests(TestCase):
    def test_birthday_in_year(self):
        leap = datetime.date(1996, 2, 29)
        self.assertEqual(birthdays.birthday_in_year(leap, 2027), datetime.date(2027, 2, 28))
        self.assertEqual(birthdays.birthday_in_year(leap, 2028), datetime.date(2028, 2, 29))
        self.assertEqual(birthdays.birthday_in_year(datetime.date(1990, 6, 15), 2027), datetime.date(2027, 6, 15))

    def test_profiles_with_birthday_on(self):
        leap = make_user(email="bisiesto@example.com")
        other = make_user(email="otro@example.com")
        CustomerProfile.objects.create(user=leap, date_of_birth=datetime.date(1996, 2, 29))
        CustomerProfile.objects.create(user=other, date_of_birth=datetime.date(1990, 2, 28))
        non_leap = set(birthdays.profiles_with_birthday_on(datetime.date(2027, 2, 28)))
        self.assertEqual({p.user for p in non_leap}, {leap, other})
        leap_year_28 = set(birthdays.profiles_with_birthday_on(datetime.date(2028, 2, 28)))
        self.assertEqual({p.user for p in leap_year_28}, {other})
        leap_year_29 = set(birthdays.profiles_with_birthday_on(datetime.date(2028, 2, 29)))
        self.assertEqual({p.user for p in leap_year_29}, {leap})
