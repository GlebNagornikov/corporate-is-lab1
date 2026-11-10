from django.db import IntegrityError, transaction

from orders.models import Order, OrderItem

from .models import Review


class ReviewError(Exception):
    pass


REVIEW_EXISTS = "Вы уже оставили отзыв на это издание."


def review_block_reason(product, user):
    if not user.is_authenticated:
        return "Войдите, чтобы оставить отзыв о доставленной покупке."
    existing = product.reviews.filter(author=user).values_list("status", flat=True).first()
    if existing == Review.Status.PENDING:
        return "Ваш отзыв ожидает модерации."
    if existing == Review.Status.REJECTED:
        return "Ваш отзыв отклонён модератором."
    if existing:
        return REVIEW_EXISTS
    if not OrderItem.objects.filter(
        product=product, order__user=user, order__status=Order.Status.DELIVERED
    ).exists():
        return "Отзыв доступен после доставки вашего заказа с этим изданием."
    return ""


def create_review(*, product, author, rating, text):
    if reason := review_block_reason(product, author):
        raise ReviewError(reason)
    try:
        with transaction.atomic():
            return Review.objects.create(product=product, author=author, rating=rating, text=text)
    except IntegrityError as error:
        if product.reviews.filter(author=author).exists():
            raise ReviewError(REVIEW_EXISTS) from error
        raise


@transaction.atomic
def moderate_review(*, review_id, decision):
    review = Review.objects.select_for_update().get(pk=review_id)
    if review.status != Review.Status.PENDING:
        raise ReviewError("Этот отзыв уже прошёл модерацию.")
    review.status = decision
    review.save(update_fields=["status"])
    return review
