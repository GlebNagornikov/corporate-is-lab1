import re

from django.core.exceptions import ValidationError


def normalize_phone(value):
    """Приводит российский номер к формату +7XXXXXXXXXX."""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10 and digits[0] == "9":
        return "+7" + digits
    raise ValidationError("Введите российский номер телефона, например +7 913 123-45-67.")
