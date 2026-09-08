from rest_framework.routers import SimpleRouter

from apps.students.views import StudentViewSet

router = SimpleRouter()
router.register("students", StudentViewSet, basename="student")

urlpatterns = router.urls
