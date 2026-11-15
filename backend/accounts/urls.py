from django.urls import include, path

from .views import SignUpView

urlpatterns = [
    path("", include("accounts.addresses")),
    path("signup/", SignUpView.as_view(), name="signup"),
]
