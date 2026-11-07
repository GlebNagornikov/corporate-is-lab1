from django.middleware.csrf import get_token
from django.urls import path
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings

from config.throttling import ShopAnonThrottle, TokenThrottle

REFRESH_COOKIE = "shop_refresh"
COOKIE_PATH = "/api/auth/"


def set_refresh_cookie(response, refresh, max_age):
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=max_age,
        path=COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="Strict",
    )


class CsrfSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()


class AccessSerializer(serializers.Serializer):
    access = serializers.CharField()


@method_decorator(never_cache, name="dispatch")
@method_decorator(csrf_protect, name="dispatch")
class SessionView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]


class CsrfView(SessionView):
    @extend_schema(responses=CsrfSerializer)
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class LoginView(SessionView):
    throttle_classes = [ShopAnonThrottle, TokenThrottle]

    @extend_schema(request=TokenObtainPairSerializer, responses={200: AccessSerializer})
    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        pair = serializer.validated_data
        response = Response({"access": pair["access"]})
        set_refresh_cookie(
            response, pair["refresh"], int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds())
        )
        return response

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'


class RefreshView(SessionView):
    @extend_schema(request=None, responses={200: AccessSerializer})
    def post(self, request):
        refresh = request.COOKIES.get(REFRESH_COOKIE)
        if not refresh:
            raise AuthenticationFailed("Сессия отсутствует.")
        serializer = TokenRefreshSerializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as error:
            raise InvalidToken(error.args[0]) from error
        return Response({"access": serializer.validated_data["access"]})

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'


class LogoutView(SessionView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        set_refresh_cookie(response, "", 0)
        return response


urlpatterns = [
    path("csrf/", CsrfView.as_view(), name="spa-csrf"),
    path("login/", LoginView.as_view(), name="spa-login"),
    path("refresh/", RefreshView.as_view(), name="spa-refresh"),
    path("logout/", LogoutView.as_view(), name="spa-logout"),
]
