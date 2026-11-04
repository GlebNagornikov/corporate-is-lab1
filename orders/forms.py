from django import forms

from .models import Order
from .services import OrderError, get_valid_promo


class CheckoutForm(forms.ModelForm):
    promo_code = forms.CharField(label="Промокод", max_length=30, required=False)

    class Meta:
        model = Order
        fields = ["full_name", "phone", "email", "delivery_method", "address", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 2})}

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
        if cleaned.get("delivery_method") == Order.Delivery.COURIER and not cleaned.get("address"):
            self.add_error("address", "Для доставки курьером укажите адрес.")
        return cleaned
