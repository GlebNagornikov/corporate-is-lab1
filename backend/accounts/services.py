from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Address, User


@transaction.atomic
def save_address(user, data, pk=None):
    User.objects.select_for_update().get(pk=user.pk)
    address = get_object_or_404(Address, pk=pk) if pk else Address(user=user)
    if address.user_id != user.pk:
        raise PermissionDenied
    for field in ("label", "city", "street", "house", "apartment", "comment", "is_primary"):
        if field in data:
            setattr(address, field, data[field])
    if not user.addresses.exclude(pk=address.pk).exists():
        address.is_primary = True
    if address.is_primary:
        user.addresses.exclude(pk=address.pk).update(is_primary=False)
    elif not user.addresses.exclude(pk=address.pk).filter(is_primary=True).exists():
        address.is_primary = True
    address.full_clean()
    address.save()
    return address


@transaction.atomic
def delete_address(user, pk):
    User.objects.select_for_update().get(pk=user.pk)
    address = get_object_or_404(Address, pk=pk, user=user)
    address.delete()
    if not user.addresses.filter(is_primary=True).exists():
        replacement = user.addresses.first()
        if replacement:
            replacement.is_primary = True
            replacement.save(update_fields=["is_primary"])
