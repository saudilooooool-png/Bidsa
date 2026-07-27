# دليل النشر — بيدسا

المنظومة ثلاث طبقات، ولكل طبقة مكان نشر مناسب:

| الطبقة | التقنية | أين تُنشر |
|---|---|---|
| الواجهة `frontend/` | Next.js 15 | **Vercel** |
| الخادم `backend/` | FastAPI + Python | Railway / Render / Fly.io (أي مضيف حاويات) |
| قاعدة البيانات | PostgreSQL 16 + pgvector (UTF8) | Neon / Supabase / Railway Postgres |

> ⚠️ Vercel يستضيف الواجهة فقط. الـ backend يحتاج عملية دائمة (جدولة APScheduler
> واتصالات قاعدة بيانات)، وقاعدة البيانات تحمل 55 ألف ترسية — كلاهما خارج نطاق Vercel.

---

## 1) قاعدة البيانات (مرة واحدة)

أنشئ قاعدة PostgreSQL على Neon أو Supabase (كلاهما يدعم `pgvector` وبترميز UTF8
افتراضيًا)، ثم خذ رابطي الاتصال:

```
DATABASE_URL      = postgresql+asyncpg://USER:PASS@HOST/DB
DATABASE_URL_SYNC = postgresql+psycopg2://USER:PASS@HOST/DB
```

طبّق المخطط ثم حمّل المستودع التاريخي (من جهازك بعد استنساخ المستودع):

```bash
cd backend
pip install -r requirements.txt
export DATABASE_URL_SYNC="postgresql+psycopg2://USER:PASS@HOST/DB"
alembic upgrade head                      # يطبق db/schema.sql + الهجرة 002

python3 scripts/etl_historical.py \
  --data-dir ../etimad-plus-viewer/data \
  --db "$DATABASE_URL_SYNC" \
  --report-out ../db/reports/historical_coverage.md
# ~75 ثانية محليًا؛ عبر الشبكة قد تستغرق دقائق أكثر. السكربت idempotent — أعده بأمان.
```

## 2) الخادم الخلفي

على Railway أو Render: أنشئ خدمة من هذا المستودع بجذر `backend/`
(يوجد `backend/Dockerfile` جاهز)، ومرّر متغيرات البيئة:

```
DATABASE_URL       = postgresql+asyncpg://...
DATABASE_URL_SYNC  = postgresql+psycopg2://...
ENABLE_SCHEDULER   = true          # الجلب الدوري من اعتماد
SECRET_KEY         = <سلسلة عشوائية 32+ حرفًا>
OPENAI_API_KEY     = <اختياري — للإثراء بالذكاء الاصطناعي>
```

ملاحظتان:
- الحاوية تشغّل `uvicorn` فقط؛ شغّل الهجرات مرة عبر أمر start مؤقت
  `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`
  (كما في docker-compose) أو نفّذها من جهازك كما في الخطوة 1.
- بعد النشر خذ الرابط العام، مثل `https://bidsa-api.up.railway.app`،
  وجرّب `GET /health` و`GET /api/v1/intel/overview`.

## 3) الواجهة على Vercel

الطريقة الأسهل — من لوحة Vercel (بلا أدوات إضافية):

1. ادخل على **vercel.com/new** وسجّل بحساب GitHub.
2. استورد المستودع `saudilooooool-png/Bidsa`.
3. في إعدادات الاستيراد حدّد **Root Directory = `frontend`**
   (سيكتشف Next.js تلقائيًا — لا تغيّر أوامر البناء).
4. أضف متغيّر البيئة:
   `API_URL = https://<رابط-الخادم-من-الخطوة-2>`
5. اضغط **Deploy**.

كل push إلى الفرع الرئيسي بعد الربط يعيد النشر تلقائيًا.

> إن نُشرت الواجهة قبل ضبط `API_URL` ستظهر صفحة خطأ عربية واضحة
> (`src/app/error.tsx`) بدل انهيار الصفحة — اضبط المتغير وأعد النشر.

### CORS

للعرض التجريبي يسمح الخادم بكل المصادر. قبل الإنتاج قيّده في
`backend/app/main.py`:

```python
allow_origins=["https://<مشروعك>.vercel.app"]
```

---

## تجربة محلية كاملة (بديل سريع عن النشر)

```bash
git clone https://github.com/saudilooooool-png/Bidsa && cd Bidsa
docker compose up --build
# ثم مرة واحدة لتحميل البيانات داخل الحاوية:
docker compose exec backend python scripts/etl_historical.py \
  --data-dir /app/data-src --db "postgresql+psycopg2://bidsa:bidsa@db:5432/bidsa"
```

- الواجهة: http://localhost:3000
- الـ API/التوثيق: http://localhost:8000/docs

(لتشغيل الـ ETL داخل الحاوية أضف في docker-compose تحت خدمة backend:
`- ./etimad-plus-viewer/data:/app/data-src:ro` ضمن volumes — أو شغّل السكربت
من جهازك مباشرة على قاعدة docker بمنفذ 5432.)
