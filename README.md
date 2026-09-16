# O'quv markazlari CRM

Ko'p markazli (multi-tenant) CRM tizimi. Foydalanuvchi uchun ekran hali yo'q —
Django admin va REST API.

| Bosqich | Mazmuni | Holati |
|---|---|---|
| 0 | Poydevor: markaz, filial, foydalanuvchi, a'zolik, audit, tenant ajratish | tayyor |
| 1 | O'quvchi yadrosi: kurs, xona, bayram, o'quvchi, guruh, jadval, dars, davomat | tayyor |
| 2-4 | `Payment`, `Salary`, `Lead` va boshqalar | hali yo'q |

---

## 1. Texnologiyalar

- Python 3.12
- Django 5.2
- Django REST Framework + SimpleJWT
- PostgreSQL

Boshqa paket ishlatilmaydi (Celery, Redis, Docker, django-tenants, drf-spectacular va h.k. yo'q).

---

## 2. Asosiy qarorlar

| # | Qaror |
|---|---|
| 1 | Custom `User` modeli birinchi migratsiyadan oldin yaratilgan |
| 2 | Login: **email + parol**. `phone` majburiy, lekin login uchun emas |
| 3 | Barcha modellarda birlamchi kalit — **UUID** |
| 4 | Pul maydonlari — `DecimalField(14, 2)`. `FloatField` hech qachon |
| 5 | `USE_TZ = True`, `TIME_ZONE = "Asia/Tashkent"` |
| 6 | Hech narsa o'chirilmaydi — `status` orqali arxivlanadi (`DELETE` metodi yo'q) |
| 7 | Bitta baza, har bir tenant modelida `center` FK |
| 8 | `on_delete=PROTECT` (CASCADE ishlatilmaydi) |

---

## 3. Noldan ishga tushirish

### 3.1. Virtual muhit

```bash
cd crm
python -m venv .venv
source .venv/Scripts/activate    # Windows (Git Bash)
source .venv/bin/activate        # Linux / macOS
```

### 3.2. Paketlar

```bash
pip install -r requirements.txt
```

### 3.3. PostgreSQL da baza va foydalanuvchi

`psql` ichida (superuser sifatida):

```sql
CREATE ROLE crm_user LOGIN PASSWORD 'sizning-parolingiz' CREATEDB;
CREATE DATABASE crm OWNER crm_user ENCODING 'UTF8';
```

> `CREATEDB` huquqi kerak — Django testlar uchun `test_crm` bazasini o'zi yaratadi.

### 3.4. `.env` fayli

```bash
cp .env.example .env
```

So'ng `.env` ichini to'ldiring:

```
SECRET_KEY=uzun-tasodifiy-qator
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=crm
DB_USER=crm_user
DB_PASSWORD=sizning-parolingiz
DB_HOST=127.0.0.1
DB_PORT=5432
```

`SECRET_KEY` yaratish:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

> `.env` `.gitignore` da — hech qachon git ga tushmaydi.

### 3.5. Migratsiya va superuser

```bash
python manage.py migrate
python manage.py createsuperuser
```

`createsuperuser` email, telefon, ism va familiya so'raydi (`username` yo'q).

### 3.6. Ishga tushirish

```bash
python manage.py runserver
```

- Admin panel: http://127.0.0.1:8000/admin/
- API: http://127.0.0.1:8000/api/

### 3.7. Testlar

```bash
python manage.py test
```

---

## 4. Loyiha strukturasi

```
config/          settings.py, urls.py, wsgi.py, asgi.py
apps/
    common/      abstract modellar, tenant mantiqi, permission, TenantViewSet
    centers/     Center, Branch
    accounts/    User, UserManager, Membership
    audit/       AuditLog, log_action()
manage.py
.env.example
requirements.txt
```

---

## 5. Modellar

### `Center` (markaz — tenant)
`name`, `slug` (unique), `status` (ACTIVE / SUSPENDED). O'zida `center` FK yo'q.

### `Branch` (filial)
`center` FK, `name`, `address`, `phone`, `status` (ACTIVE / CLOSED).
`unique_together = (center, name)`.

### `User` (foydalanuvchi)
`email` (USERNAME_FIELD), `phone` (unique, majburiy), `first_name`, `last_name`,
`is_active`, `is_staff`, `date_joined`.

**Diqqat:** `User` tenant modeli emas — bir odam bir nechta markazda ishlashi mumkin,
shuning uchun unda `center` FK yo'q.

### `Membership` (a'zolik / xodim)
`user`, `center`, `branches` (M2M, **bo'sh = barcha filiallar**),
`role` (OWNER / ADMIN / TEACHER / ACCOUNTANT), `status` (ACTIVE / INACTIVE), `started_at`.
`unique_together = (user, center, role)`.
`branches` ichidagi har bir filial shu markazga tegishli bo'lishi shart.

### `AuditLog` (audit jurnali)
`center`, `user` (null — tizim amali), `created_at`, `action` (CREATE / UPDATE / DELETE),
`object_type`, `object_id`, `old_values`, `new_values`, `ip_address`.

**O'zgarmas (immutable):** himoya ikki qatlamda:

- Model darajasi — mavjud yozuvni `save()` va `delete()` qilish `ValidationError` beradi
- QuerySet darajasi — `AuditLogQuerySet` da `update()` va `delete()` ham yopiq

Ikkinchi qatlam majburiy: Django'da `QuerySet.update()` va `QuerySet.delete()` model
metodlarini **umuman chaqirmaydi** va to'g'ridan-to'g'ri SQL yuboradi. `bulk_update()`
ham `update()` ustida ishlaydi, shuning uchun u ham avtomatik yopiladi.

Admin panelda qo'shish/o'zgartirish/o'chirish yopiq.

`old_values` / `new_values` JSONField ga yoziladi, shuning uchun `model_snapshot()`
`date`, `Decimal` va UUID kabi qiymatlarni matnga aylantiradi — 2-bosqichdagi
to'lov va maosh summalari ham shu yo'l bilan xavfsiz yoziladi.

---

## 6. Audit qanday yoziladi

Django signal **ishlatilmaydi** — signal ichida "kim o'zgartirdi" ma'lum bo'lmaydi
va kod ko'rinmas bo'lib qoladi. Buning o'rniga `apps/audit/services.py` dagi funksiya
view/serializer/admin ichidan ochiq chaqiriladi:

```python
log_action(center, user, action, instance, old_values=None, new_values=None, ip_address=None)
```

`old_values` va `new_values` — faqat **o'zgargan maydonlar**.
Masalan filialning faqat telefoni o'zgarsa:

```json
{"old_values": {"phone": ""}, "new_values": {"phone": "+998712001122"}}
```

Auditga yoziladigan amallar: `Branch` va `Membership` yaratish/o'zgartirish (API va admin),
`Center` yaratish/o'zgartirish (admin).

---

## 7. Tenant (markaz) ajratish

Har bir API so'rovida `X-Center-Id` sarlavhasi yuboriladi.

| Holat | Natija |
|---|---|
| Sarlavha bor, shu markazda ACTIVE a'zolik bor | Ishlaydi |
| Sarlavha bor, ACTIVE a'zolik yo'q | **403** |
| Sarlavha yo'q, bitta ACTIVE a'zolik bor | Avtomatik o'sha markaz, **200** |
| Sarlavha yo'q, bir nechta ACTIVE a'zolik | **400** + javobda markazlar ro'yxati |
| Umuman ACTIVE a'zolik yo'q | **403** |

Aniqlangan markaz `request.center` ga yoziladi.

**Qattiq qoida:** begona markaz obyekti so'ralsa — **404** qaytadi, 403 emas.
403 "bunday obyekt bor, lekin ruxsating yo'q" degani, bu ma'lumot sizishi bo'lardi.
`TenantViewSet.get_queryset()` filtri buni avtomatik ta'minlaydi.

`perform_create()` esa `center` ni majburiy o'rnatadi — mijoz yuborgan `center` qiymati
**e'tiborsiz qoldiriladi**.

---

## 8. API endpointlar

| Metod | Yo'l | Izoh |
|---|---|---|
| POST | `/api/auth/login/` | JWT olish (email + parol) |
| POST | `/api/auth/refresh/` | Tokenni yangilash |
| GET | `/api/me/` | Foydalanuvchi + barcha a'zoliklari va markazlari |
| GET, POST, PATCH | `/api/branches/` | Filiallar (tenant filtri bilan) |
| GET, POST, PATCH | `/api/memberships/` | Xodimlar (tenant filtri bilan) |

`Center` uchun API yo'q — markazlarni faqat platforma egasi Django admin orqali yaratadi.
`DELETE` metodi hech qayerda yo'q — `status` o'zgartiriladi.

### Misollar

Login:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@crm.uz", "password": "parol"}'
```

Filiallar ro'yxati:

```bash
curl http://127.0.0.1:8000/api/branches/ \
  -H "Authorization: Bearer <access-token>" \
  -H "X-Center-Id: <markaz-uuid>"
```

Filial yaratish:

```bash
curl -X POST http://127.0.0.1:8000/api/branches/ \
  -H "Authorization: Bearer <access-token>" \
  -H "X-Center-Id: <markaz-uuid>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Chilonzor filiali", "address": "Toshkent"}'
```

Filialni yopish (o'chirish emas):

```bash
curl -X PATCH http://127.0.0.1:8000/api/branches/<id>/ \
  -H "Authorization: Bearer <access-token>" \
  -H "X-Center-Id: <markaz-uuid>" \
  -H "Content-Type: application/json" \
  -d '{"status": "CLOSED"}'
```

---

## 9. Django admin

Ro'yxatdan o'tgan: `Center`, `Branch`, `User`, `Membership`, `AuditLog`.

- Barcha sarlavhalar o'zbek tilida
- `Branch` va `Membership` da markaz bo'yicha filtr
- `User` uchun custom admin — `username` maydoni yo'q, email asosida
- `AuditLog` — faqat o'qish uchun

---

## 10. Testlar

```bash
python manage.py test
```

Prompt talab qilgan 12 ta holat:

| # | Test | Joyi |
|---|---|---|
| 1 | Email + parol bilan login, JWT qaytadi | `apps/accounts/tests.py::test_01_login_returns_jwt` |
| 2 | Begona markaz filiali -> 404 | `apps/common/tests.py::test_02_foreign_branch_returns_404` |
| 3 | Bir nechta a'zolik, sarlavhasiz -> 400 | `apps/common/tests.py::test_03_multiple_memberships_without_header_returns_400` |
| 4 | Bitta a'zolik, sarlavhasiz -> 200 | `apps/common/tests.py::test_04_single_membership_without_header_returns_200` |
| 5 | INACTIVE a'zolik -> 403 | `apps/common/tests.py::test_05_inactive_membership_returns_403` |
| 6 | Mijoz yuborgan `center` e'tiborsiz qoldiriladi | `apps/common/tests.py::test_06_client_center_is_ignored_on_create` |
| 7 | Bir odam ikki markazda faol, ikkalasiga kiradi | `apps/common/tests.py::test_07_user_in_two_centers_can_reach_both` |
| 8 | AuditLog faqat o'zgargan maydonni saqlaydi | `apps/audit/tests.py::test_08_update_writes_only_changed_fields` |
| 9 | AuditLog yozuvini o'zgartirib bo'lmaydi | `apps/audit/tests.py::test_09_existing_log_cannot_be_changed` |
| 10 | AuditLog yozuvini o'chirib bo'lmaydi | `apps/audit/tests.py::test_10_log_cannot_be_deleted` |
| 11 | Filiallari bor markazni o'chirib bo'lmaydi | `apps/centers/tests.py::test_11_center_with_branches_cannot_be_deleted` |
| 12 | Begona filial `Membership.branches` ga qo'shilmaydi | `apps/accounts/tests.py::test_12_foreign_branch_rejected` |

Ustiga qo'shimcha 14 ta test — jami **26 ta**. Muhimlari:

| Test | Nimani himoya qiladi |
|---|---|
| `test_09b_queryset_update_is_blocked` | `AuditLog.objects.filter(...).update()` — model `save()` ni chetlab o'tadi |
| `test_09c_bulk_update_is_blocked` | `bulk_update()` ham yopiq |
| `test_08e_date_field_is_stored_as_text` | Auditda `date` (va kelajakda `Decimal`) buzilmaydi |
| `test_12c/12d_api_rejects_foreign_branch` | Begona filial HTTP yo'lida ham to'siladi (`clean()` M2M `.add()` da ishlamaydi) |
| `test_07b_delete_method_is_not_allowed` | `DELETE` → 405 |
| `test_02b_list_shows_only_own_center` | Ro'yxatda ham tenant filtri bor |

---

## 11. DEBUG=False bilan ishlatish

`.env` da:

```
DEBUG=False
ALLOWED_HOSTS=example.uz,www.example.uz
SECURE_HTTPS=True
```

`SECURE_HTTPS=True` HSTS, SSL redirect va secure cookie larni yoqadi —
faqat haqiqatan HTTPS orqali ishlaganda qo'yiladi. Shu holatda
`check --deploy` hech qanday ogohlantirish bermaydi.

Statik fayllarni yig'ish va tekshirish:

```bash
python manage.py collectstatic
python manage.py check --deploy
```


---

# 1-bosqich: o'quvchi yadrosi

## 12. Yangi modellar

```
apps/courses/         Course, Room, Holiday
apps/students/        Student
apps/study_groups/    Group, GroupSchedule, GroupStudent
apps/lessons/         Lesson, Attendance
```

App nomi `groups` emas, `study_groups` — `django.contrib.auth.models.Group` bilan
chalkashmasligi uchun. Auth'ning `Group` i admin panelidan olib tashlangan: rollar
`Membership` orqali boshqariladi.

Barchasi `TenantModel` dan meros oladi (UUID, `center` FK, vaqt maydonlari),
barcha FK `on_delete=PROTECT`, hech qayerda `DELETE` yo'q.

| Model | Muhim jihati |
|---|---|
| `Course` | `duration_months` dan guruhning `end_date` i hisoblanadi |
| `Room` | `branch` ga bog'langan; `branch.center == center` tekshiriladi |
| `Holiday` | shu sanaga dars generatsiya qilinmaydi |
| `Student` | `User` EMAS — tizimga kirmaydi. `phone` da unique yo'q (aka-uka) |
| `Group` | `teacher` — `Membership`, roli TEACHER va holati ACTIVE bo'lishi shart |
| `GroupSchedule` | haftalik jadval, Dushanba = 0 (Python `date.weekday()`) |
| `GroupStudent` | oraliq model: `joined_at` / `left_at` 2-bosqichdagi to'lov uchun |
| `Lesson` | `teacher` guruhnikidan farq qilishi mumkin (o'rinbosar) |
| `Attendance` | `unique_together = (lesson, student)` |

`GroupStudent` da bitta `(group, student)` juftligi uchun faqat bitta `ACTIVE`
yozuv bo'la oladi — `UniqueConstraint` + `condition=Q(status="ACTIVE")`.
Chiqib ketgandan keyin qayta qo'shilish mumkin.

---

## 13. Biznes mantiq

Hammasi `services.py` fayllarida oddiy funksiya. Model `save()` ichida yashirilmagan,
Django signal ishlatilmagan.

### `apps/lessons/services.py`

- **`check_conflicts(lesson, pending=())`** — shu markazda, bir xil sanada,
  `PLANNED`/`HELD` holatda, bir xil xona **yoki** bir xil o'qituvchi bilan vaqti
  kesishgan darslarni topadi. O'qituvchi ziddiyati **filialdan qat'i nazar**.
  `CANCELLED` va `MOVED` hisobga olinmaydi. `pending` — hali saqlanmagan darslar
  (bitta generatsiya ichida ular ham bir-biriga to'qnashishi mumkin).
- **`generate_lessons(group)`** — sanadan sanaga oddiy sikl: `date.weekday()` ni
  jadval bilan solishtiradi, bayramni o'tkazib yuboradi. Kalendar kutubxonasi yo'q.
  Faqat kelajakdagi `PLANNED` darslar o'chirilib qayta yaratiladi;
  `HELD`, `CANCELLED`, `MOVED` va o'tmishdagi darslarga tegilmaydi.
  Idempotent. Ziddiyat topilsa butun amal bekor bo'ladi.
- **`move_lesson(...)`** — eskisi `MOVED` bo'ladi, `moved_to` to'ldiriladi,
  yangisi `PLANNED` bo'lib yaratiladi, audit yoziladi. `HELD` darsni ko'chirib bo'lmaydi.
- **`mark_attendance(lesson, items, membership)`** — butun guruh bitta so'rovda.
  Kelajakdagi darsga qo'yilmaydi. Belgilangach dars `PLANNED` → `HELD`.

### `apps/study_groups/services.py`

- **`activate_group(group)`** — `ACTIVE` qiladi va darslarni generatsiya qiladi
- **`apply_schedule_change(group)`** — jadval o'zgargach qayta generatsiya
- **`sync_teacher(group)`** — faqat kelajakdagi `PLANNED` darslarning o'qituvchisi
  yangilanadi (3-bosqichdagi maosh hisobi uchun tarix saqlanadi)
- **`add_student(group, student)`** — limitdan oshsa rad etilmaydi, `warning` qaytadi

### Audit qachon yoziladi

| Holat | Audit |
|---|---|
| Dars ko'chirildi | yoziladi |
| Mavjud davomat o'zgartirildi | yoziladi |
| O'tgan darsga orqaga qaytib davomat qo'yildi | yoziladi |
| Dars kunining o'zida birinchi marta belgilash | **yozilmaydi** (shovqin bo'lmasin) |

---

## 14. 1-bosqich API endpointlari

| Metod | Yo'l | Izoh |
|---|---|---|
| GET, POST, PATCH | `/api/courses/` | kurslar |
| GET, POST, PATCH | `/api/rooms/` | xonalar |
| GET, POST, PATCH | `/api/holidays/` | bayram kunlari |
| GET, POST, PATCH | `/api/students/` | o'quvchilar |
| GET, POST, PATCH | `/api/groups/` | guruhlar |
| POST | `/api/groups/<id>/activate/` | ACTIVE + darslar generatsiyasi |
| POST | `/api/groups/<id>/cancel/` | CANCELLED + kelajakdagi darslar ham bekor qilinadi |
| GET, POST | `/api/groups/<id>/schedules/` | jadval (o'zgarish → qayta generatsiya) |
| PATCH | `/api/groups/<id>/schedules/<sid>/` | jadval qatorini tahrirlash |
| GET, POST | `/api/groups/<id>/students/` | guruh o'quvchilari |
| POST | `/api/groups/<id>/students/<eid>/leave/` | `left_at` + status LEFT |
| GET | `/api/lessons/` | filtrlar: `group`, `date_from`, `date_to`, `teacher`, `status` |
| PATCH | `/api/lessons/<id>/` | faqat `topic` va `status` (→ CANCELLED) |
| POST | `/api/lessons/<id>/move/` | darsni ko'chirish |
| GET, POST | `/api/lessons/<id>/attendance/` | ommaviy davomat |

`DELETE` hech qayerda yo'q. `/api/lessons/` ga `POST` — 405: darslar faqat
generatsiya orqali paydo bo'ladi. `Group.status` — `read_only`: u faqat
`/activate/` va `/cancel/` orqali o'zgaradi, aks holda guruh ACTIVE bo'lib
qolib darslar generatsiya bo'lmasligi mumkin edi.

**Ro'yxatlar sahifalangan** (`PAGE_SIZE=50`):

```json
{"count": 128, "next": "...?page=2", "previous": null, "results": [...]}
```

Barcha serializerlarda `center` — `read_only`. FK maydonlar (`course`, `branch`,
`room`, `teacher`, `student`) markazga tegishliligi tekshiriladi: begona obyekt
yuborilsa 400 va maydon nomi bilan aniq xato. Begona obyektning **o'zi** so'ralsa — 404.

### Misollar

Guruhni faollashtirish:

```bash
curl -X POST http://127.0.0.1:8000/api/groups/<id>/activate/ \
  -H "Authorization: Bearer <token>" -H "X-Center-Id: <markaz-uuid>"
# {"group": {...}, "lessons_created": 51}
```

Ommaviy davomat:

```bash
curl -X POST http://127.0.0.1:8000/api/lessons/<id>/attendance/ \
  -H "Authorization: Bearer <token>" -H "X-Center-Id: <markaz-uuid>" \
  -H "Content-Type: application/json" \
  -d '{"items": [
        {"student": "<uuid>", "status": "PRESENT"},
        {"student": "<uuid>", "status": "ABSENT", "note": "Kasal"}
      ]}'
# {"lesson_status": "HELD", "attendances": [...]}
```

Darsni ko'chirish:

```bash
curl -X POST http://127.0.0.1:8000/api/lessons/<id>/move/ \
  -H "Authorization: Bearer <token>" -H "X-Center-Id: <markaz-uuid>" \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-10-15", "start_time": "14:00", "end_time": "15:30", "room": "<uuid>"}'
```

---

## 15. 1-bosqich testlari

```bash
python manage.py test
```

Prompt talab qilgan 22 ta holat:

| # | Test | Joyi |
|---|---|---|
| 1 | Begona markaz o'qituvchisi biriktirilmaydi | `study_groups/tests.py::test_01_foreign_center_teacher_rejected` |
| 2 | TEACHER bo'lmagan xodim o'qituvchi bo'lolmaydi | `study_groups/tests.py::test_02_non_teacher_membership_rejected` |
| 3 | Begona filial / xona biriktirilmaydi | `study_groups/tests.py::test_03_foreign_branch_or_room_rejected` |
| 4 | `end_date` kurs davomiyligidan hisoblanadi | `study_groups/tests.py::test_04_end_date_computed_from_course_duration` |
| 5 | Jadvalsiz guruh ACTIVE bo'lmaydi | `study_groups/tests.py::test_05_group_without_schedule_cannot_activate` |
| 6 | Darslar soni aniq to'g'ri | `lessons/tests.py::test_06_activation_generates_exact_lessons` |
| 7 | Bayram kuniga dars yaratilmaydi | `lessons/tests.py::test_07_holiday_is_skipped` |
| 8 | Xona ziddiyati → 400, birorta dars yaratilmaydi | `lessons/tests.py::test_08_room_conflict_blocks_everything` |
| 9 | O'qituvchi ziddiyati, boshqa filialda ham | `lessons/tests.py::test_09_teacher_conflict_across_branches` |
| 10 | CANCELLED dars ziddiyat emas | `lessons/tests.py::test_10_cancelled_lesson_is_not_a_conflict` |
| 11 | Jadval o'zgarganda HELD tegilmaydi | `lessons/tests.py::test_11_schedule_change_keeps_held_lessons` |
| 12 | O'qituvchi almashsa faqat kelajak PLANNED | `lessons/tests.py::test_12_teacher_change_updates_only_future_planned` |
| 13 | Kelasi kunning darsiga davomat yo'q | `lessons/tests_attendance.py::test_13_future_lesson_cannot_be_marked` |
| 14 | Davomatdan keyin dars HELD | `lessons/tests_attendance.py::test_14_marking_moves_lesson_to_held` |
| 15 | O'tgan davomat tahriri auditga tushadi | `lessons/tests_attendance.py::test_15_editing_past_attendance_writes_audit` |
| 16 | Guruhda bo'lmagan o'quvchiga davomat yo'q | `lessons/tests_attendance.py::test_16_student_joined_later_is_rejected` |
| 17 | Bir o'quvchi ikki marta ACTIVE bo'lolmaydi | `study_groups/tests.py::test_17_same_student_cannot_be_active_twice` |
| 18 | Ko'chirishda eskisi MOVED + `moved_to` | `lessons/tests_attendance.py::test_18_move_marks_old_as_moved` |
| 19 | HELD darsni ko'chirib bo'lmaydi | `lessons/tests_attendance.py::test_19_held_lesson_cannot_be_moved` |
| 20 | Begona guruh / dars / o'quvchi → 404 | `study_groups`, `lessons`, `students` `::test_20_*` |
| 21 | Limitdan oshsa qo'shiladi + `warning` | `study_groups/tests.py::test_21_over_limit_adds_with_warning` |
| 22 | Generatsiya idempotent | `lessons/tests.py::test_22_generation_is_idempotent` |

Jami **97 ta test** (0-bosqich 26 + 1-bosqich 43 + kod tekshiruvidan keyin 28).

---

## 16. Demo ma'lumot

Bazada tayyor: `Bilim Ziyo o'quv markazi` ichida 1 kurs (Ingliz tili, 6 oy),
2 xona, 1 bayram kuni, `ENG-B-01` guruhi (Dushanba/Chorshanba 09:00–10:30),
5 o'quvchi va generatsiya qilingan **51 dars** — bayram kuni o'tkazib yuborilgan.

Kirish ma'lumotlari `DEMO_LOGIN.txt` faylida (`.gitignore` da).

---

## 17. Rol huquqlari

0-bosqichda rol darajasidagi huquqlar ataylab yo'q edi. Kod tekshiruvi
ko'rsatdiki bu shunchaki "nozik huquq" emas, balki **huquq oshirish teshigi**:
o'qituvchi `PATCH /api/memberships/<o'zi>/ {"role": "OWNER"}` yuborib egaga
aylana olardi. Endi har bir viewset rolga bog'langan.

| Amal | OWNER | ADMIN | ACCOUNTANT | TEACHER |
|---|:-:|:-:|:-:|:-:|
| Xodimlarni ko'rish va boshqarish (`/memberships/`) | ✅ | ✅ | ❌ | ❌ |
| Filial, kurs, xona, bayram, o'quvchi yaratish/tahrirlash | ✅ | ✅ | ❌ | ❌ |
| Guruh yaratish, faollashtirish, bekor qilish, jadval | ✅ | ✅ | ❌ | ❌ |
| Guruhga o'quvchi qo'shish / chiqarish | ✅ | ✅ | ❌ | ❌ |
| Darsni ko'chirish (`/move/`) | ✅ | ✅ | ❌ | ❌ |
| Davomat qo'yish va mavzu yozish | ✅ | ✅ | ❌ | faqat o'z darsida |
| Ro'yxatlarni o'qish (guruh, dars, o'quvchi, kurs…) | ✅ | ✅ | ✅ | ✅ |

Qoidalar `apps/common/permissions.py` dagi `HasCenterRole` da:

- `write_roles` — yozish uchun rollar (standart: OWNER, ADMIN)
- `read_roles` — o'qish uchun rollar (`None` = har qanday faol a'zo)
- `action_roles` — alohida `@action` uchun rollar
- `teacher_field` — obyekt darajasida tekshiruv: TEACHER faqat `lesson.teacher`
  o'zi bo'lgan darsni o'zgartira oladi

Qo'shimcha qoida: **hech kim o'zining rolini yoki holatini o'zgartira olmaydi** —
ADMIN ham o'zini OWNER qila olmaydi.

---

## 18. Xavfsizlik

| Chora | Holati |
|---|---|
| Tenant ajratish | `X-Center-Id`, begona obyekt → 404, `center` serverda o'rnatiladi |
| Rol huquqlari | `HasCenterRole`, obyekt darajasida ham |
| SUSPENDED markaz | ishlamaydi → 403 |
| Audit o'zgarmasligi | `save`, `delete`, `QuerySet.update`, `bulk_update` — hammasi yopiq |
| Login brute-force | `10/min` tezlik cheklovi (`ScopedRateThrottle`), IP `NUM_PROXIES` bo'yicha aniqlanadi |
| Token muddati | access 1 soat, refresh 7 kun, yangilashda eski refresh qora ro'yxatga |
| Parol validatorlari | Django'ning 4 ta standart validatori yoqilgan |
| HTTPS | `SECURE_HTTPS=True` → HSTS + SSL redirect + secure cookie |
| Sahifalash | `PAGE_SIZE=50` — bitta javobda minglab yozuv kelmaydi |

### `NUM_PROXIES` — nega muhim

DRF mijoz IP'sini tezlik cheklovi uchun ishlatadi. `NUM_PROXIES` sozlanmagan
bo'lsa, DRF IP'ni `X-Forwarded-For` sarlavhasidan oladi — mijoz esa bu
sarlavhani o'zi yozadi. Natijada har safar boshqa soxta IP yuborib
(`10.0.0.1`, `10.0.0.2`, …) cheklovni cheksiz aylanib o'tish mumkin bo'ladi.

`.env` da:

| Muhit | Qiymat |
|---|---|
| Proxy yo'q (lokal, `runserver`, to'g'ridan-to'g'ri gunicorn) | `NUM_PROXIES=0` |
| Bitta ishonchli proxy ortida (nginx, Caddy) | `NUM_PROXIES=1` |
| Ikkita (nginx + Cloudflare) | `NUM_PROXIES=2` |

`0` bo'lganda faqat `REMOTE_ADDR` ishlatiladi va soxta sarlavha e'tiborsiz
qoldiriladi. Qiymatni proxy sonidan **katta** qilib qo'ymang — u holda
mijozning o'zi yozgan qiymatga qaytib qolasiz.

> **Eslatma — cache va worker'lar.** Tezlik cheklovi Django cache'ida
> hisoblanadi. Standart `LocMemCache` har bir worker jarayonida **alohida**
> ishlaydi, ya'ni 4 ta worker bo'lsa cheklov amalda `10/min` emas, har
> worker'da `10/min` bo'ladi. Haqiqiy umumiy cheklov kerak bo'lsa,
> umumiy cache (Redis/Memcached) kerak — lekin u yangi paket va
> infratuzilma talab qiladi, shuning uchun bu bosqichda qo'shilmadi.

Hali qilinmagan (keyingi bosqichlarda ko'rib chiqiladi):

- **Logout endpointi yo'q** — qora ro'yxat mexanizmi yoqilgan, lekin foydalanuvchi
  o'z tokenini bekor qiladigan endpoint hali qo'shilmagan
- `Group.status = FINISHED` faqat Django admin orqali qo'yiladi
- Bayramni **o'chirish** darslarni qaytarmaydi (sanasini o'zgartirish qaytaradi);
  o'chirgandan keyin guruhni qayta `/activate/` qilish kerak
