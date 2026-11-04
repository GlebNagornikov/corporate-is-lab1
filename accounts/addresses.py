from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path

from .models import Address
from .services import delete_address as delete_address
from .services import save_address as save_address


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ["label", "city", "street", "house", "apartment", "comment", "is_primary"]


@login_required
def address_book(request, pk=None):
    address = get_object_or_404(Address, pk=pk, user=request.user) if pk else None
    if request.method == "POST" and request.POST.get("action") == "delete" and pk:
        delete_address(request.user, pk)
        return redirect("addresses")
    form = AddressForm(request.POST or None, instance=address)
    if request.method == "POST" and form.is_valid():
        save_address(request.user, form.cleaned_data, pk)
        return redirect("addresses")
    return render(
        request,
        "accounts/addresses.html",
        {"addresses": request.user.addresses.all(), "form": form, "editing": address},
    )


urlpatterns = [
    path("addresses/", address_book, name="addresses"),
    path("addresses/<int:pk>/", address_book, name="address-edit"),
]
