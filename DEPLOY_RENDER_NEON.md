# Render + Neon: bepul joylashtirish

Bu versiya mahalliy kompyuterda SQLite, hostingda `DATABASE_URL` orqali PostgreSQL bilan ishlaydi. Render + Neon hisoblarini o‘zingiz yaratasiz; bu ZIP ularni avtomatik ochmaydi va sayt hali joylashtirilmagan.

## 1. Mavjud GitHub repozitoriyingizni yangilang

ZIP ichidagi `quiz-platform` papkasining **ichidagi fayllarni** kompyuteringizdagi mavjud `quiz-platform` papkasiga ko‘chiring, bir xil nomli dastur fayllarini almashtiring. Mavjud `.git` va `data` papkalarini o‘chirmang. `server.py`, `requirements.txt` va `render.yaml` repozitoriy ildizida yonma-yon tursin.

PowerShell da:

```powershell
git add .
git commit -m "Add Neon PostgreSQL and Render deployment"
git push
```

`.gitignore` bazani va `.env` ni chetlatadi. Parollar yoki Neon connection stringni kodga yozmang. Avval ular Git ga kiritilgan bo‘lsa, `.gitignore` ularni tarixdan olib tashlamaydi; maxfiy kalit/parolni almashtirish kerak.

## 2. Neon bazasini yarating

1. https://neon.com saytida ro‘yxatdan o‘ting.
2. Bepul **Free** rejada yangi loyiha yarating.
3. **Connect** bo‘limidan connection stringni nusxalang. U `postgresql://` bilan boshlanadi.
4. Manzilni parol kabi saqlang; chatga yoki GitHub ga yubormang. Neon bergan TLS parametrlarini (`sslmode=require`, mavjud bo‘lsa `channel_binding=require`) o‘chirmang.

## 3. Render xizmatini yarating

1. https://render.com saytida GitHub bilan kiring.
2. **New → Web Service** ni tanlang va mavjud `umid-web/Quiz-lesson` repozitoriyini ulang.
3. Quyidagi sozlamalarni kiriting:

| Sozlama | Qiymat |
| --- | --- |
| Branch | `main` |
| Runtime / Language | Python 3 |
| Root Directory | `server.py` ildizda bo‘lsa bo‘sh qoldiring; ichki papkada bo‘lsa aynan o‘sha papka yo‘li |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python server.py` |
| Instance Type | Free |

**Environment** bo‘limiga:

| Kalit | Qiymat |
| --- | --- |
| `DATABASE_URL` | Neon bergan to‘liq connection string |
| `BOOTSTRAP_ADMIN_USERNAME` | O‘zingiz tanlagan admin login |
| `BOOTSTRAP_ADMIN_PASSWORD` | Kamida 10 belgili noyob parol |
| `COOKIE_SECURE` | `1` |

Render portni o‘zi beradi. Persistent Disk yoki Render Postgres yaratish kerak emas: bu loyiha tashqi Neon bazasidan foydalanadi. `render.yaml` Blueprint orqali o‘rnatish uchun ham bor; qo‘lda Web Service ochilganda yuqoridagi qiymatlarni kiriting.

## 4. Joylashtiring va tekshiring

**Deploy Web Service** ni bosing. O‘rnatish tugagach Render bergan HTTPS manzilni oching. `/admin` sahifasiga o‘zingiz belgilagan login/parol bilan kiring. Birinchi ochilishda jadvallar va 50 savollik bank avtomatik yaratiladi. Keyingi deploylar mavjud bank yoki parolni qayta yozmaydi.

Telefon orqali bitta testni yakunlab, kompyuterdagi admin panelida ism va natijani ko‘ring. Shundan keyin havolani ishtirokchilarga yuboring. Admin paroli environmentda faqat birinchi yaratilishda ishlatiladi; uni o‘zgartirish mavjud admin parolini avtomatik almashtirmaydi.

## Muhim farqlar

- Free tariflar cheklangan. Render faol bo‘lmaganda uyquga o‘tadi; qayta ochilishi vaqt olishi mumkin. Testdan oldin saytni ochib tekshiring. Bepul tariflar shartlari o‘zgarishi mumkin.
- Natijalar Neon bazasida; Render mahalliy diski o‘chsa ham o‘sha `DATABASE_URL` qayta ulanganida baza saqlanadi. Neon loyihasini o‘chirish natijalarni yo‘qotadi.
- Kompyuterdagi SQLite natijalari yangi Neon bazasiga avtomatik ko‘chirilmaydi. Ular eski `data` papkasida saqlanadi. Yangi baza dastlab bo‘sh bo‘ladi.
- Lokal sinashda `DATABASE_URL` berilmasa avvalgidek SQLite ishlaydi. Lokal HTTP uchun `COOKIE_SECURE=1` qo‘ymang.
- Bir dona xizmat nusxasidan foydalaning. Loyiha kichik o‘quv guruhi uchun; katta yuklamada alohida unumdorlik va xavfsizlik tekshiruvi kerak.

## Xatolar

- `requirements.txt` yoki `server.py` topilmadi: Render dagi Root Directory noto‘g‘ri.
- Admin ma’lumotlari so‘ralmoqda: ikkala `BOOTSTRAP_ADMIN_*` qiymatini tekshiring, parol 10 belgidan kam bo‘lmasin.
- Ulanish ishlamayapti: `DATABASE_URL` ni Neon dagi Connect bo‘limidan qayta nusxalang, TLS parametrlarini saqlang. Uni terminal loglari yoki skrinshot orqali ulashmang.
- `No module named psycopg`: Build Command `pip install -r requirements.txt` bo‘lsin.

Manbalar: https://render.com/docs/free ; https://render.com/docs/web-services ; https://neon.com/docs/get-started-with-neon/connect-neon ; https://www.psycopg.org/psycopg3/docs/basic/usage.html
