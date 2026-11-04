from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("", views.OrderListView.as_view(), name="list"),
    path("<int:pk>/", views.OrderDetailView.as_view(), name="detail"),
    path("<int:pk>/cancel/", views.order_cancel, name="cancel"),
]
