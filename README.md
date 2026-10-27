# Viloyatlararo booking platformasi

## Hozir ishlayotgan Telegram bot

Rootdagi `src/` — Telegram’da ishlayotgan Node.js + MongoDB Atlas botidir.

Asosiy imkoniyatlar:

- ixcham va tushunarli 2×2 yo‘lovchi menyusi;
- tayyor reys yoki shaxsiy safar buyurtmasi;
- har bosqichda orqaga qaytish va jarayonni bekor qilish;
- tugallanmagan buyurtmani davom ettirish;
- yo‘nalishlar, bo‘sh joylar va boshlang‘ich narxlar katalogi;
- qat’iy O‘zbekiston telefon raqami va yo‘lovchi ismi validatsiyasi;
- ikki bosqichli buyurtma bekor qilish;
- MongoDB tranzaksiyasi bilan joylarni atomik band qilish;
- admin tasdig‘i, individual narx taklifi va statistikasi.

```powershell
.\start-bot.ps1
.\status-bot.ps1
.\stop-bot.ps1
npm.cmd test
```

Maxfiy kalitlar faqat `.env` ichida saqlanadi va repoga kiritilmaydi.

## Keyingi avlod arxitekturasi

Loyihaning tasdiqlangan yangi arxitekturasi `bot/` ichida joylashgan:

- [Tuzatilgan TZ v1.1](docs/TZ_v1.1.md)
- [Python bot qo‘llanmasi](bot/README.md)
- [Asosiy ilova](bot/app)
- [Testlar](bot/tests)

Yangi stack: Python 3.12, aiogram 3, FastAPI, PostgreSQL, Redis va Celery.

`bot/` ichidagi Python/PostgreSQL servis hali production Telegram tokeniga ulanmagan. U to‘lov provayderlari,
PostgreSQL darajasidagi booking va kengaytirilgan rol panellari uchun rejalashtirilgan arxitekturadir.

Hozirgi ishlayotgan bot MongoDB Atlas’dan foydalanadi. Python servis productionga o‘tkazilganda asosiy baza
PostgreSQL, Redis esa FSM, rate limit va vazifalar navbati uchun ishlatiladi.
