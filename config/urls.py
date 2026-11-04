from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from config.api_docs import ShopSchemaView, ShopSwaggerView, ShopTokenView
from config.health import healthz

urlpatterns = [
    path("api/schema/", ShopSchemaView.as_view(), name="api-schema"),
    path("api/docs/", ShopSwaggerView.as_view(), name="api-docs"),
    path("", include("orders.reporting")),
    path("", include("orders.payments")),
    path("", include("catalog.restock")),
    path("", include("catalog.comparison")),
    path("", include("catalog.wishlist")),
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/", include("employees.urls")),
    path("api/catalog/", include("catalog.api")),
    path("api/auth/token/", ShopTokenView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include("cart.api")),
    path("api/", include("orders.api")),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("cart/", include("cart.urls")),
    path("orders/", include("orders.urls")),
    path("", include("catalog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if "debug_toolbar" in settings.INSTALLED_APPS:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
