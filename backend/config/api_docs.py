from django.conf import settings
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.views import TokenObtainPairView

from .throttling import ShopAnonThrottle, TokenThrottle

MANAGER_ACCESS_ERRORS = {
    401: OpenApiResponse(description="Требуется Bearer-токен."),
    403: OpenApiResponse(description="Недостаточно прав сотрудника."),
}


class DocsPermission(BasePermission):
    def has_permission(self, request, view):
        return settings.DEBUG or bool(request.user and request.user.is_staff)


class ShopSchemaView(SpectacularAPIView):
    permission_classes = [DocsPermission]


class ShopSwaggerView(SpectacularSwaggerView):
    permission_classes = [DocsPermission]
    url_name = "api-schema"


class ShopTokenView(TokenObtainPairView):
    throttle_classes = [ShopAnonThrottle, TokenThrottle]
