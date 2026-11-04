# Create your views here.
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from .filters import ProductFilter
from .forms import ReviewForm
from .models import Category, Product, Review


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

    def get_queryset(self):
        return (
            Product.objects.active()
            .select_related("category__parent")
            .with_rating()
            .prefetch_related("images")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["reviews"] = self.object.reviews.filter(is_published=True).select_related("author")
        context["can_review"] = (
            user.is_authenticated and not self.object.reviews.filter(author=user).exists()
        )
        context["review_form"] = ReviewForm()
        return context


class ReviewCreateView(LoginRequiredMixin, View):
    def post(self, request, slug):
        product = get_object_or_404(Product.objects.active(), slug=slug)
        if Review.objects.filter(product=product, author=request.user).exists():
            messages.error(request, "Вы уже оставили отзыв на этот товар.")
            return redirect(product)
        form = ReviewForm(request.POST)
        if form.is_valid():
            form.instance.product = product
            form.instance.author = request.user
            form.save()
            messages.success(request, "Спасибо за отзыв!")
        else:
            messages.error(request, "Отзыв не сохранён: проверьте оценку и текст.")
        return redirect(product)
