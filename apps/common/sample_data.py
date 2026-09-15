"""Testlar uchun kichik yordamchi funksiyalar (tashqi paketsiz)."""

from datetime import date

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.models import Membership, User
from apps.centers.models import Branch, Center

PAROL = "Juda-Kuchli-Parol-2026"


def make_user(email, phone, **extra):
    return User.objects.create_user(
        email=email,
        phone=phone,
        first_name=extra.pop("first_name", "Ism"),
        last_name=extra.pop("last_name", "Familiya"),
        password=extra.pop("password", PAROL),
        **extra,
    )


def make_center(name, slug, status=Center.Status.ACTIVE):
    return Center.objects.create(name=name, slug=slug, status=status)


def make_branch(center, name, **extra):
    return Branch.objects.create(center=center, name=name, **extra)


def make_membership(user, center, role=Membership.Role.ADMIN, status=Membership.Status.ACTIVE):
    return Membership.objects.create(
        user=user,
        center=center,
        role=role,
        status=status,
        started_at=date(2026, 1, 1),
    )


def get_token(client, email, password=PAROL):
    """Login qilib access token qaytaradi.

    Login endpointida tezlik cheklovi bor va cache testlar orasida saqlanadi,
    shuning uchun hisobni tozalaymiz. Cheklovning o'zi alohida testda
    tekshiriladi (apps/accounts/tests.py::LoginThrottleTest).
    """
    cache.clear()
    response = client.post(
        "/api/auth/login/",
        {"email": email, "password": password},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    return response.json()["access"]


def auth_headers(token, center=None):
    headers = {"Authorization": f"Bearer {token}"}
    if center is not None:
        headers["X-Center-Id"] = str(center.id)
    return headers


# --- 1-bosqich yordamchilari ---

from datetime import timedelta  # noqa: E402

from apps.courses.models import Course, Holiday, Room  # noqa: E402
from apps.students.models import Student  # noqa: E402
from apps.study_groups.models import Group, GroupSchedule, GroupStudent  # noqa: E402


def next_weekday(from_date, weekday):
    """from_date dan boshlab birinchi kelgan shu hafta kuni (Dushanba = 0)."""
    return from_date + timedelta(days=(weekday - from_date.weekday()) % 7)


def make_course(center, name="Ingliz tili", duration_months=6, lessons_per_week=2, price="500000.00"):
    return Course.objects.create(
        center=center,
        name=name,
        duration_months=duration_months,
        lessons_per_week=lessons_per_week,
        default_price=price,
    )


def make_room(center, branch, name="101-xona", capacity=15):
    return Room.objects.create(center=center, branch=branch, name=name, capacity=capacity)


def make_holiday(center, on_date, name="Bayram"):
    return Holiday.objects.create(center=center, date=on_date, name=name)


def make_student(center, first_name="Ali", last_name="Valiyev", **extra):
    return Student.objects.create(
        center=center, first_name=first_name, last_name=last_name, **extra
    )


def make_teacher(center, email, phone, **extra):
    """O'qituvchi: User + TEACHER roli bilan ACTIVE Membership."""
    user = make_user(email, phone, **extra)
    make_membership(user, center, role=Membership.Role.TEACHER)
    return Membership.objects.get(user=user, center=center, role=Membership.Role.TEACHER)


def make_group(center, course, branch, teacher, name="ENG-01", start_date=None, **extra):
    group = Group(
        center=center,
        course=course,
        branch=branch,
        teacher=teacher,
        name=name,
        start_date=start_date or date(2026, 1, 1),
        **extra,
    )
    group.full_clean()
    group.save()
    return group


def make_schedule(group, weekday, room, start="09:00", end="10:30"):
    schedule = GroupSchedule(
        center=group.center,
        group=group,
        weekday=weekday,
        start_time=start,
        end_time=end,
        room=room,
    )
    schedule.full_clean()
    schedule.save()
    return schedule


def make_enrollment(group, student, joined_at=None, **extra):
    enrollment = GroupStudent(
        center=group.center,
        group=group,
        student=student,
        joined_at=joined_at or group.start_date,
        **extra,
    )
    enrollment.full_clean()
    enrollment.save()
    return enrollment


class TenantApiTestCase(TestCase):
    """
    Tayyor muhit: bitta markaz, filial, kurs, xona, o'qituvchi va
    admin foydalanuvchi tokeni bilan.
    """

    def setUp(self):
        self.center = make_center("A markaz", "a-markaz")
        self.branch = make_branch(self.center, "Chilonzor filiali")
        self.course = make_course(self.center)
        self.room = make_room(self.center, self.branch)
        self.teacher = make_teacher(self.center, "teacher@a.uz", "+998900000011")

        self.admin_user = make_user("admin@a.uz", "+998900000010")
        make_membership(self.admin_user, self.center)
        self.token = get_token(self.client, "admin@a.uz")
        self.headers = auth_headers(self.token, self.center)

    @staticmethod
    def rows(response):
        """Sahifalangan ro'yxat javobidan yozuvlarni oladi."""
        data = response.json()
        return data["results"] if isinstance(data, dict) and "results" in data else data

    def api(self, method, url, data=None):
        """Autentifikatsiya va X-Center-Id bilan JSON so'rov."""
        kwargs = {"headers": self.headers}
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(self.client, method)(url, **kwargs)
