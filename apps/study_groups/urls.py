from rest_framework.routers import SimpleRouter

from apps.study_groups.views import GroupViewSet

router = SimpleRouter()
router.register("groups", GroupViewSet, basename="group")

urlpatterns = router.urls
