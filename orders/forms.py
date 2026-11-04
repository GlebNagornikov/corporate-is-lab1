from django import forms

from accounts.models import Address

from .models import Order
from .services import OrderError, get_valid_promo
from .validators import normalize_phone


class CheckoutForm(forms.ModelForm):
    address_book = forms.ModelChoiceField(
        label="Сохранённый адрес", queryset=Address.objects.none(), required=False
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["address_book"].queryset = user.addresses.all()

    promo_code = forms.CharField(label="Промокод", max_length=30, required=False)

    class Meta:
        model = Order
        fields = ["full_name", "phone", "email", "delivery_method", "address", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 2})}

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])

    def clean_promo_code(self):
        code = self.cleaned_data["promo_code"].strip()
        if code:
            try:
                get_valid_promo(code)
            except OrderError as error:
                raise forms.ValidationError(str(error)) from error
        return code

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("address_book"):
            cleaned["address"] = cleaned["address_book"].snapshot
        if cleaned.get("delivery_method") == Order.Delivery.COURIER and not cleaned.get("address"):
            self.add_error("address", "Для доставки курьером укажите адрес.")
        return cleaned
