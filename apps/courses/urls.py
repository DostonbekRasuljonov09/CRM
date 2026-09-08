from rest_framework.routers import SimpleRouter

from apps.courses.views import CourseViewSet, HolidayViewSet, RoomViewSet

router = SimpleRouter()
router.register("courses", CourseViewSet, basename="course")
router.register("rooms", RoomViewSet, basename="room")
router.register("holidays", HolidayViewSet, basename="holiday")

urlpatterns = router.urls
