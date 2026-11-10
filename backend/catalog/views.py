# Create your views here.
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import DetailView, ListView

from .filters import ProductFilter
from .forms import ReviewForm
from .models import Category, Product, Review
from .reviews import ReviewError, create_review, review_block_reason


def redirect_after_action(request, fallback):
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(fallback)


class ProductListView(ListView):
    template_name = "catalog/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        queryset = (
            Product.objects.active()
            .select_related("category")
            .with_rating()
            .order_by("-created_at")  # Meta.ordering не действует на запросы с GROUP BY
        )
        self.filterset = ProductFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = self.filterset
        slug = self.request.GET.get("category")
        context["current_category"] = Category.objects.filter(slug=slug).first() if slug else None
        query = self.request.GET.get("q", "").strip()
        if query and not context["page_obj"].object_list:
            context["suggestions"] = Product.objects.active().similar_to(query)[:5]
        return context


class ProductDetailView(DetailView):
    template_name = "catalog/product_detail.html"
    context_object_name = "product"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        variants = list(self.object.variants.all())
        self.has_variants = any(not variant.is_default for variant in variants)
        self.available_variants = [
            variant for variant in variants if variant.is_active and not variant.is_default
        ]
        variant_id = kwargs.get("variant_id")
        self.variant = None
        if variant_id is not None:
            self.variant = next(
                (variant for variant in self.available_variants if variant.pk == variant_id),
                None,
            )
            if self.variant is None:
                raise Http404
        elif self.available_variants:
            first = next(
                (variant for variant in self.available_variants if variant.stock > 0),
                self.available_variants[0],
            )
            return redirect(first)
        return self.render_to_response(self.get_context_data(object=self.object))

    def get_object(self, queryset=None):
        from .caching import product_key

        key = product_key(self.kwargs["slug"])
        product = cache.get(key)
        if product is None:
            product = super().get_object(queryset)
            cache.set(key, product)
        return product

    def get_queryset(self):
        return (
            Product.objects.active()
            .select_related("category__parent")
            .with_rating()
            .prefetch_related("images", "variants")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["variant"] = self.variant
        context["available_variants"] = self.available_variants
        context["sale_item"] = self.variant or self.object
        context["can_buy"] = context["sale_item"].stock > 0 and (
            self.variant is not None or not self.has_variants
        )
        context["reviews"] = self.object.reviews.filter(
            status=Review.Status.APPROVED
        ).select_related("author")
        context["can_review"] = not review_block_reason(self.object, self.request.user)
        context["review_form"] = ReviewForm()
        return context


class ReviewCreateView(LoginRequiredMixin, View):
    def post(self, request, slug):
        product = get_object_or_404(Product.objects.active(), slug=slug)
        form = ReviewForm(request.POST)
        if form.is_valid():
            try:
                create_review(product=product, author=request.user, **form.cleaned_data)
            except ReviewError as error:
                messages.error(request, str(error))
            else:
                messages.success(request, "Ваш отзыв ожидает модерации.")
        else:
            messages.error(request, "Отзыв не сохранён: проверьте оценку и текст.")
        return redirect(product)
