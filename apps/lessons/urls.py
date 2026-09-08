from rest_framework.routers import SimpleRouter

from apps.lessons.views import LessonViewSet

router = SimpleRouter()
router.register("lessons", LessonViewSet, basename="lesson")

urlpatterns = router.urls
