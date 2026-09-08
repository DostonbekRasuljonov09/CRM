"""Asosiy URL jadvali."""

from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "O'quv markazlari CRM"
admin.site.site_title = "CRM boshqaruvi"
admin.site.index_title = "Boshqaruv paneli"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.centers.urls")),
    path("api/", include("apps.courses.urls")),
    path("api/", include("apps.students.urls")),
    path("api/", include("apps.study_groups.urls")),
    path("api/", include("apps.lessons.urls")),
]
