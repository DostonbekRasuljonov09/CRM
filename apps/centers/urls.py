from rest_framework.routers import SimpleRouter

from apps.centers.views import BranchViewSet

router = SimpleRouter()
router.register("branches", BranchViewSet, basename="branch")

urlpatterns = router.urls
