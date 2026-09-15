from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import MembershipViewSet, MeView, ThrottledLoginView

router = SimpleRouter()
router.register("memberships", MembershipViewSet, basename="membership")

urlpatterns = [
    path("auth/login/", ThrottledLoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
] + router.urls
