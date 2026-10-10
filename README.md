# Kirim-Chiqim nazorati (Django REST Framework)

Shaxsiy moliya (kirim va chiqimlar) nazorati uchun REST API.

- **Modellar:** `Category`, `Wallet`, `Transaction` (o'zimiz yozilgan)
- **Serializerlar:** oddiy `serializers.Serializer` (ModelSerializer yo'q) — barcha logika shu yerda:
  validatsiya, `create`/`update`, balansni atomik o'zgartirish, filtrlash, statistika
- **Views:** DRF generic view'lar, JWT autentifikatsiya (simplejwt: access 30 daqiqa, refresh 7 kun)
- **Admin panel:** barcha modellar ro'yxatdan o'tgan
- **Hujjatlar:** Swagger UI + ReDoc (drf-spectacular), Postman collection

## Ishga tushirish

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py makemigrations accounts finance
python manage.py migrate   # token_blacklist jadvallari ham yaratiladi
python manage.py createsuperuser   # admin panel uchun
python manage.py runserver
```

| Manzil | Tavsif |
|---|---|
| `/app/` | **Frontend** (veb-ilova, asosiy sahifa) |
| `/api/docs/` | Swagger UI |
| `/api/redoc/` | ReDoc |
| `/api/schema/` | OpenAPI schema (yaml) |
| `/admin/` | Admin panel |

Testlar: `python manage.py test`

## Postman

`docs/KirimChiqim.postman_collection.json` faylini Postman'ga **Import** qiling.
Avval **Register** yoki **Login** ni ishga tushiring — `access` va `refresh` avtomatik saqlanadi
va qolgan so'rovlarda `Authorization: Bearer {{access}}` sifatida yuboriladi.
Access tugasa **Refresh token** so'rovini ishga tushiring.
Yaratilgan `id` lar ham (kategoriya, hamyon, tranzaksiya) avtomatik saqlanadi.

## Endpointlar

| Metod | URL | Tavsif |
|---|---|---|
| POST | `/api/auth/register/` | Ro'yxatdan o'tish |
| POST | `/api/auth/login/` | Access va refresh token olish |
| POST | `/api/auth/refresh/` | Access tokenni yangilash |
| POST | `/api/auth/logout/` | Refresh tokenni bekor qilish (blacklist) |
| GET/PUT/PATCH | `/api/auth/me/` | Profil |
| POST | `/api/auth/change-password/` | Parolni almashtirish |
| GET/POST | `/api/categories/` | Kategoriyalar (`?type=income\|expense`) |
| GET/PUT/PATCH/DELETE | `/api/categories/{id}/` | Kategoriya |
| GET/POST | `/api/wallets/` | Hamyonlar |
| GET/PUT/PATCH/DELETE | `/api/wallets/{id}/` | Hamyon |
| GET/POST | `/api/transactions/` | Kirim-chiqimlar (filtr, qidiruv, tartiblash) |
| GET/PUT/PATCH/DELETE | `/api/transactions/{id}/` | Tranzaksiya |
| GET | `/api/summary/` | Jami kirim/chiqim va kategoriyalar kesimi |

Tranzaksiya filtrlari: `type`, `category`, `wallet`, `date_from`, `date_to`,
`min_amount`, `max_amount`, `search`, `ordering`, `page`, `page_size`.

## Asosiy biznes qoidalar (serializers.py)

- Har bir foydalanuvchi faqat o'z ma'lumotlarini ko'radi (boshqasiniki `404`).
- Tranzaksiya turi (kirim/chiqim) **kategoriya** turidan olinadi.
- Kirim hamyon balansini oshiradi, chiqim kamaytiradi; mablag' yetmasa `400`.
- Tranzaksiyani tahrirlash/o'chirishda balans qayta hisoblanadi (`transaction.atomic`).
- Tranzaksiyasi bor kategoriyani o'chirib yoki turini o'zgartirib bo'lmaydi.
- Hamyon balansini to'g'ridan-to'g'ri o'zgartirib bo'lmaydi.
- Kelajak sanasi qabul qilinmaydi.

## Struktura

```
templates/  frontend (app.html: bitta faylli veb-ilova)
config/     sozlamalar, asosiy urls (Swagger/ReDoc shu yerda)
accounts/   ro'yxatdan o'tish, login, profil
finance/    modellar, serializerlar, view'lar, admin, testlar
docs/       Postman collection
```
