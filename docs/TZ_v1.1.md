# Viloyatlararo booking Telegram boti — TZ v1.1

Status: amalga oshirish uchun tasdiqlangan bazaviy spetsifikatsiya  
Vaqt zonasi: ma’lumotlar UTC, foydalanuvchiga `Asia/Tashkent`  
Asosiy stack: Python 3.12, aiogram 3, FastAPI, PostgreSQL, Redis, Celery

## 1. Maqsad va chegaralar

Tizim yo‘lovchiga Telegram ichida O‘zbekiston hududlari orasidagi reysni topish, 15 daqiqaga joy ushlash, to‘lovni tasdiqlash, elektron bilet olish va buyurtmani boshqarish imkonini beradi. Operator, haydovchi, admin va super admin uchun rolga mos menyular taqdim etiladi.

MVP faqat admin yaratgan reyslarni sotadi. Istalgan manzil/vaqt bo‘yicha individual taxi buyurtmasi, aniq o‘rindiq sxemasi, promokod, referal, butun taxi va Web Admin keyingi bosqichga kiradi.

## 2. MVP tarkibi

MVPga kiradi:

- o‘zbek va rus tillarida ro‘yxatdan o‘tish;
- telefonni Telegram kontakti orqali tasdiqlash va shartlarga rozilik;
- faol marshrut, sana, transport turi va reys bo‘yicha qidirish;
- raqamsiz 1–5 joyni tranzaksion hold qilish;
- qo‘lda to‘lov tasdig‘i, keyin Payme/Click adapterlari;
- elektron bilet raqami va QR;
- faol/tugagan/bekor qilingan buyurtmalar;
- bekor qilish va qaytariladigan summani hisoblash;
- Telegram ichidagi admin va operator boshqaruvi;
- haydovchini reysga biriktirish va asosiy haydovchi oqimi;
- audit, outbox bildirishnomalari, hold va eslatma vazifalari;
- asosiy statistika va CSV eksport;
- Docker Compose, migratsiya, test va healthcheck.

MVPdan tashqarida:

- taxi uchun butun mashina;
- tanlanadigan aniq o‘rindiqlar va vagon sxemasi;
- Uzum va naqd/avans oqimi;
- promokod, referal va bonus;
- ommaviy Web Admin;
- poyezd operatorining rasmiy API integratsiyasi.

## 3. Rollar va RBAC

Rollar: `passenger`, `driver`, `operator`, `admin`, `super_admin`.

- `passenger`: qidirish, hold, to‘lov, bekor qilish, tarix, baholash.
- `driver`: biriktirilgan reyslar, yo‘lovchilar, boarding/no-show, reysni boshlash/yakunlash.
- `operator`: buyurtmalar, qo‘lda band qilish, haydovchi biriktirish, mijozga xabar.
- `admin`: operator huquqlari hamda marshrut, reys, tarif, foydalanuvchi, to‘lov va hisobotlar.
- `super_admin`: rollar va tizim sozlamalari.

Rollar `users`, `roles`, `user_roles` orqali ko‘p-rol modelida saqlanadi. Har bir himoyalangan handler middleware orqali DBdagi amaldagi rolni tekshiradi. Dastlabki super admin `.env`dagi Telegram ID orqali bootstrap qilinadi.

## 4. Asosiy biznes qoidalari

### BR-01 — narx ierarxiyasi

Marshrutning mavjud tariflari doim `taxi > bus > train`. Mavjud bo‘lmagan transport narxi `NULL`. Tariflar bitta `route_fares` yozuvida saqlanadi va ilova hamda DB constraint orqali tekshiriladi. Reys narxi yaratilganda tarifdan snapshot olinadi; keyingi tarif o‘zgarishi eski reys/buyurtma narxini o‘zgartirmaydi.

### BR-02 — pul

Barcha summalar UZSda butun son. Float ishlatilmaydi. Ko‘rinish: `180 000 so‘m`.

### BR-03 — hold

Foydalanuvchi “To‘lash”ni bosganda booking `pending_payment` holatida yaratiladi va `hold_expires_at = now() + hold_minutes`. Standart `hold_minutes=15`. Muddati o‘tgan hold Celery vazifasi bilan bir daqiqada bo‘shatiladi.

### BR-04 — double booking

Hold yaratish va bo‘shatish PostgreSQL tranzaksiyasida bajariladi. Reys `SELECT ... FOR UPDATE` bilan bloklanadi, `seats_available` tekshiriladi va shu tranzaksiyada kamaytiriladi. DB constraint: `0 <= seats_available <= seats_total`.

### BR-05 — sana

Reys bugundan maksimum `booking_horizon_days=30` kun oldindan sotiladi. `booking_cutoff_minutes=60` qolganda yangi booking yopiladi. Har ikkisi admin sozlamasi.

### BR-06 — yo‘lovchilar

MVPda taxi 1–4, bus/train 1–5; umumiy maksimum 5. Aniq limit reys sig‘imi va transport turi bo‘yicha hisoblanadi.

### BR-07 — taxi

MVPda faqat umumiy taxi va raqamsiz joy. Butun mashina keyingi bosqich.

### BR-08 — bekor qilish

- `>24 soat`: 100%;
- `6–24 soat`: 70%;
- `1–6 soat`: 30%;
- `<1 soat`: 0%;
- kompaniya bekor qilsa: 100%.

Foizlar `settings`da versiyalangan holda saqlanadi. Booking bekor qilinganda amaldagi qoida snapshoti va hisoblangan summa yoziladi. Bekor qilish ikki bosqichli tasdiqdan so‘ng tranzaksiyada joyni qaytaradi.

### BR-09 — bolalar

MVPda alohida bepul joy logikasi yo‘q; izoh maydonida qayd qilinadi.

### BR-10 — telefon

Format `+998XXXXXXXXX`. Faqat `contact.user_id == from.id` bo‘lgan kontakt qabul qilinadi. Telefon o‘zgarsa qayta tasdiqlanadi.

### BR-11 — komissiya

Transport turi bo‘yicha foiz `transport_types.commission_pct`. Booking tasdiqlanganda komissiya snapshoti va summasi saqlanadi.

## 5. Booking state machine

Asosiy oqim:

```text
pending_payment -> confirmed -> completed
       |              |            |
       v              v            v
    expired        cancelled     no_show
                      |
                      v
               refund_pending -> refunded
```

- FSMdagi tanlovlar booking emas; faqat “To‘lash” bosilganda DB booking yaratiladi.
- `expired`, `cancelled`, `refunded`, `completed`, `no_show` terminal yoki nazorat qilinadigan holatlar.
- Har o‘tish servis qatlamida ruxsat etilgan transition jadvali bo‘yicha tekshiriladi.
- Booking, payment va refund statuslari alohida enumlar.

## 6. Yo‘lovchi oqimi

### Ro‘yxatdan o‘tish

1. Til: O‘zbekcha / Русский.
2. Qisqa tanishtiruv.
3. O‘z kontaktini yuborish.
4. Terms va Privacy havolalari, versiyasi bilan rozilik.
5. Asosiy menyu.

Ro‘yxatdan o‘tgan foydalanuvchining `/start` buyrug‘i menyuni ochadi. Tugallanmagan Redis FSM bo‘lsa “Davom ettirish / Qaytadan boshlash” chiqadi.

### Menyu

- Buyurtma berish;
- Mening buyurtmalarim;
- Narxlar;
- Yordam / Aloqa;
- Sozlamalar;
- rolga mos qo‘shimcha menyu.

### Booking FSM

`from_region -> to_region -> date -> transport_type -> trip -> passengers -> pickup -> passenger_names -> confirm -> payment -> done`.

Har ekranda Orqaga va Bekor qilish mavjud. Redis TTL 24 soat. Har bosqich `funnel_events`ga yoziladi.

`pickup`: taxi uchun matn yoki Telegram location majburiy; bus/train uchun admin belgilagan bekat/vokzal.

## 7. To‘lov

MVP default: operator/admin qo‘lda tasdiqlaydi. Payme va Click adapterlari feature flag bilan ulanadi.

Avtomatik provider oqimi:

1. Booking `pending_payment` va hold bilan yaratiladi.
2. Payment `created` holatida, provider invoice yaratiladi.
3. Webhook provider imzosi bilan tekshiriladi.
4. `(provider, external_id)` unique idempotentlik kaliti.
5. Summa booking summasiga teng bo‘lishi shart.
6. Faol hold bo‘lsa booking `confirmed`.
7. Hold tugagan bo‘lsa reys bloklanib joy qayta olinadi; joy bo‘lmasa 100% refund boshlanadi.
8. Karta ma’lumotlari saqlanmaydi.

Provider `raw_payload` sanitizatsiya qilinib, hajmi cheklanib saqlanadi.

## 8. Bildirishnomalar

Barcha transactional xabarlar DB outbox orqali yaratiladi. Worker Telegram limitiga mos throttling, retry va exponential backoff ishlatadi. Telegram `403` qaytarsa `users.is_blocked_bot=true`.

Majburiy hodisalar: payment reminder (10-daqiqa), hold expiry, tasdiq+bilet, 24 soat/2 soat reminder, haydovchi biriktirish, reys o‘zgarishi/bekor qilinishi, refund, rating so‘rovi.

Outbox yozuvi: `deduplication_key`, `user_id`, `type`, `payload`, `scheduled_at`, `status`, `attempts`, `next_attempt_at`, `locked_at`, `sent_at`, `last_error`.

## 9. Ma’lumotlar modeli

Asosiy jadvallar:

- `users`, `roles`, `user_roles`, `user_consents`, `data_deletion_requests`;
- `regions`, `routes`, `route_fares`, `price_history`;
- `transport_types`, `trip_templates`, `trips`;
- `drivers`, `vehicles`, `trip_driver_assignments`;
- `bookings`, `booking_passengers`, `booking_events`;
- `payments`, `refunds`;
- `ratings`;
- `notification_outbox`;
- `funnel_events`;
- `audit_log`, `settings`.

Barcha biznes vaqtlar `TIMESTAMPTZ` va UTC. Pul `BIGINT`. Asosiy PK `BIGINT`; tashqi ko‘rinadigan booking number alohida unique qiymat: `TB-YYYYMMDD-NNNNN`.

Muhim indekslar:

- `trips(route_id, depart_at, transport_type_id, status)`;
- `bookings(user_id, status)`;
- partial `bookings(hold_expires_at) WHERE status='pending_payment'`;
- `payments(provider, external_id)` unique;
- `notification_outbox(status, scheduled_at)`;
- `funnel_events(session_id, created_at)`.

## 10. Admin, operator va haydovchi

Admin: marshrut/reys/tarif, haftalik shablon, buyurtma qidirish, manual payment, refund, driver/vehicle, user block, xabar, statistika, sozlamalar.

Operator: booking, manual booking, driver assignment va mijozga xabar; tarif/role/settings yo‘q.

Haydovchi: bugungi/keyingi biriktirilgan reyslar, passenger manifest, started/picked-up/no-show/done. Narx va passenger ma’lumotini o‘zgartira olmaydi.

Har mutatsiya append-only `audit_log`ga `actor`, `action`, `entity`, `before`, `after`, `request_id`, `created_at` bilan yoziladi. Runtime DB roli audit jadvalida UPDATE/DELETE huquqiga ega emas.

## 11. API va texnik arxitektura

- FastAPI: `/webhooks/telegram`, provider callbacklar, `/health/live`, `/health/ready`.
- Telegram webhook headeridagi secret doim tekshiriladi.
- Aiogram dispatcher FastAPI endpointdan update qabul qiladi.
- PostgreSQL: yakuniy biznes holatining yagona manbasi.
- Redis: FSM, rate limit, Celery broker; AOF yoqiladi.
- Celery worker: outbox, hold expiry, reminders, trip generation.
- Celery Beat: periodik scheduler; faqat bitta beat instance.
- Nginx: TLS termination va request limit.

Webhook tezda update’ni tekshiradi va handlerga uzatadi. Sekin broadcast/export/provider retry ishlari workerga beriladi.

## 12. Xavfsizlik

- secretlar faqat `.env`/secret manager;
- Telegram webhook secret header;
- user uchun sliding-window rate limit: 3 amal/soniya;
- bir foydalanuvchiga maksimum 3 faol `pending_payment`;
- parametrli ORM querylar;
- PII loglarda maskalanadi;
- DB TLS va disk encryption; telefon qidiruvi uchun shifrlangan qiymat bilan birga HMAC blind index;
- terms/privacy versiyalangan consent;
- ma’lumotni o‘chirish so‘rovi va moliyaviy yozuvlarni anonimlashtirish siyosati;
- admin mutatsiyalarida RBAC va audit;
- dependency scanning va secret scanning CI’da.

Huquqiy saqlash muddatlari alohida yurist tasdig‘idan o‘tadi.

## 13. Kuzatuvchanlik va SLO

- JSON strukturaviy log, har update/request uchun `request_id`;
- Sentry xato kuzatuvi;
- metrikalar: update latency, DB latency, holds, payments, outbox lag, Telegram 403/429;
- readiness PostgreSQL va Redisni tekshiradi;
- p95 ichki handler vaqti ≤1 s, Telegram tashqi yetkazish vaqti alohida o‘lchanadi;
- uptime maqsadi 99.5%.

## 14. Test strategiyasi

- unit: BR-01, pul, cancellation, status transitions, hold;
- integration: haqiqiy PostgreSQL/Redis test container;
- concurrency: 50 parallel so‘rov va bitta oxirgi joy — aynan bittasi muvaffaqiyatli;
- payment contract: duplicate webhook, bad signature, wrong amount, expired hold;
- E2E: Telegram test bot;
- load: 500 virtual user;
- service layer coverage ≥80%.

## 15. Deploy va backup

Muhitlar: dev, staging, production. Docker Compose MVP uchun; keyinchalik orkestratsiya mumkin. Deploy ketma-ketligi: image build, backup, `alembic upgrade head`, healthcheck, webhook set, smoke test.

PostgreSQL kunlik backup tashqi storage’ga, 7 kun saqlash. Haftalik avtomatik restore testi. Redis biznes haqiqat manbasi emas, ammo AOF yoqiladi.

## 16. Bosqichlar

1. Foundation: model, migratsiya, config, observability, CI.
2. MVP yadro: registration, search, hold, manual payment, admin, cancellation.
3. Payme/Click: provider adapterlar, webhook, refund.
4. Driver va notifications: assignment, manifest, reminders, rating.
5. Reporting/beta: statistika, CSV, load va security test.
6. Expansion: full taxi, promos, referrals, Uzum, Mini App.

## 17. Qabul mezonlari

1. `/start`dan manual/online payment tasdig‘igacha uz/ru oqim ishlaydi.
2. BR-01 ilova va DB darajasida buzilmaydi.
3. 50 parallel oxirgi-joy testida double booking yo‘q.
4. Hold 15 daqiqa ±1 daqiqada bo‘shaydi.
5. Duplicate payment webhook bookingni bir marta tasdiqlaydi.
6. Refund BR-08 bo‘yicha butun sonlarda to‘g‘ri.
7. Barcha admin/operator mutatsiyalari auditda.
8. Reminderlar 24 va 2 soat oldin outboxga tushadi.
9. 500-user testida ichki handler p95 ≤1 s.
10. Toza serverda README bo‘yicha 30 daqiqada staging ishga tushadi.

## 18. Birinchi release uchun qabul qilingan defaultlar

- barcha 14 hudud mavjud, real marshrutlarni admin faollashtiradi;
- marketplace/hamkor modeliga tayyor, lekin settlement MVPdan tashqarida;
- umumiy taxi, raqamsiz joy;
- manual payment birinchi ishlaydigan usul;
- support kontakti `.env`/settings orqali;
- Telegram admin interfeysi MVP boshqaruv paneli;
- PostgreSQL yagona production DB; MongoDB ishlatilmaydi.
