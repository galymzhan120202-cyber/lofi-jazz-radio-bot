# Jazz Lo-Fi Radio Bot — Setup нұсқаулығы

Код пен pipeline толық дайын (`jazz_video_gen.py`, `scheduler.py`, `.github/workflows/upload.yml`).
Бұл бот AITechShorts-тан түбегейлі басқаша: Shorts емес, **күніне 1 рет, кездейсоқ
70-110 минуттық** jazz музыка видеосын (loop фон + үздіксіз треклист) жасап, ұзақ-форматты
видео ретінде жүктейді. Скрипт/дауыс/субтитр жоқ.

Төмендегі қадамдарды тек сіз қолмен жасай аласыз (браузерде/сыртқы сервистерде).

## 1. Жаңа YouTube арна

1. Жаңа Google аккаунт ашыңыз (немесе қазіргі аккаунтта қосымша арна құрыңыз — Brand Account).
2. YouTube Studio-да арнаны jazz lounge нишасына сай атаумен, суретпен баптаңыз
   (қолданыстағы арна: **Velvet Jazz Lounge**, @VelvetJazzLoungeKZ).
3. Атауды/псевдонимді өзгерту кезінде абай болыңыз: YouTube бірнеше рет қатарынан
   сәтсіз атау жіберсеңіз (себебі кез келген болуы мүмкін — валидация тым сезімтал)
   **24 сағатқа rate-limit** қояды. Handle (псевдоним) бөлек, тезірек өзгереді.

## 2. Google Cloud OAuth (жүктеу үшін міндетті)

1. https://console.cloud.google.com — жаңа жоба жасаңыз (мыс. `lofijazzradiobot`).
2. **YouTube Data API v3**-ті қосыңыз (APIs & Services → Library).
3. **OAuth consent screen** баптаңыз (External).
4. **Credentials → Create Credentials → OAuth client ID → Desktop app** жасап, JSON жүктеп алыңыз → осы файлды `client_secrets.json` деп осы папкаға салыңыз.
5. Жергілікті бір рет `python jazz_video_gen.py` іске қосыңыз — браузерде жаңа арнамен логин болып, `youtube_token.json` автоматты жасалады.
6. **Маңызды:** OAuth consent screen-ды бірден **"In production"** күйіне ауыстырыңыз (Testing емес)!
   Testing статусында refresh token тек 7 күннен кейін мерзімі бітеді — AITechShorts-та
   дәл осы себептен upload үзіліп қалған болатын. `youtube.upload` — sensitive (restricted
   емес) scope, 100 пайдаланушыдан аз болғанда Google верификациясы керек емес.

**Маңызды:** OAuth логин кезінде дәл жаңа Jazz арнаға тиесілі Google аккаунтпен кіріңіз, әйтпесе видео басқа арнаға жүктеледі.

## 3. GitHub repo + Secrets

1. Жаңа бөлек GitHub repo ашыңыз (мыс. `lofi-jazz-radio-bot`), осы папканы push етіңіз.
2. Repo → Settings → Secrets and variables → Actions → төмендегі 5 Secret қосыңыз:
   - `JAZZ_PEXELS_API_KEY` — 4-қадамды қараңыз
   - `JAZZ_TELEGRAM_NOTIFY_TOKEN`
   - `JAZZ_TELEGRAM_NOTIFY_CHAT_ID`
   - `JAZZ_CLIENT_SECRETS_JSON` — `client_secrets.json` файлының толық мазмұны
   - `JAZZ_YOUTUBE_TOKEN_JSON` — `youtube_token.json` файлының толық мазмұны (2-қадамнан кейін пайда болады)

   Telegram-ды AITechShorts-пен ортақ бот/chat арқылы пайдалануға болады — хабарлама
   мәтінінде "Velvet Jazz Lounge" деп көрсетіледі, шатаспайсыз.

**Custom thumbnail туралы:** `thumbnail_gen.py` әр видеоға брендтелген thumbnail
(vinyl/rain window/piano/city night сахналары) автоматты жасайды және
`youtube.thumbnails().set()` арқылы қояды. Бұған **толық** `youtube` scope керек
(`youtube.upload` жеткіліксіз) — `client_secrets.json` мен `youtube_token.json`
осы жаңартылған кодпен қайта жасалуы керек (ескі токен escpe қалса, 403 қатесі
шығады, жай warning ретінде логталады, upload үзілмейді). Сондай-ақ **арна
телефон нөмірімен расталған болуы керек** — расталмаса, thumbnail орнатылмайды
(YouTube шектеуі, API-мен айналып өту мүмкін емес): YouTube Studio → Настройки →
Канал → Расширенные настройки → "Подтверждение номера телефона".

## 4. Музыка — YouTube Audio Library (КРИТИКАЛЫҚ ҚАДАМ)

Бұл бот AITechShorts-тағы Pexels/Openverse автоматты fetch тәсілінен **әдейі бас тартады**:
Openverse-тің jazz каталогы тым тапшы (тексерілді: "jazz" сұранысына небәрі 38 нәтиже,
"smooth jazz" — 2, "lofi jazz" — 0), әрі Jamendo-дан келетін тректің Content ID claim
тудыру тәуекелі бар (авторлық правасын толық бұзбай, таза жеке монетизация ашылатындай болу
үшін бұл тәуекел мүлдем алынып тасталды).

**Орнына — тек YouTube Audio Library:**
1. https://www.youtube.com/audiolibrary → **Music** → Genre фильтрінен **"Jazz"** таңдаңыз.
2. Кемінде **25-30 трек** жүктеп алыңыз (жиынтығы 100+ мин болатындай — сонда бір видео
   ішінде трек қайталанбайды). Ұзын тректерге басымдық беріңіз.
3. Барлық жүктелген файлды осы папканың `music/` ішіне салыңыз.
4. Кейбір трек "Attribution required" деп белгіленген болса, `music/track_info.json`
   файлына жазба қосыңыз (мысал файлда бар):
   ```json
   {
     "track_filename.mp3": {
       "title": "Track Title",
       "creator": "Artist Name",
       "attribution_required": true,
       "attribution_text": "\"Track Title\" by Artist Name (YouTube Audio Library)"
     }
   }
   ```
   Attribution керек емес тректер үшін жазба міндетті емес (бот файл атауын өзі көрсетеді).

**Неге бұл маңызды:** YouTube Audio Library — Google-дың өзі YouTube монетизациясы үшін
арнайы тексерген кітапхана, Content ID claim мүлдем болмайды. Бұл — таза, claim-сіз
монетизацияның негізгі кепілі.

## 5. Фон видео (Pexels API — автоматты, жарқын/түрлі-түсті)

Фон loop видео **қолмен жинақталмайды** — `jazz_video_gen.py` әр жүктеу алдында
[Pexels Video API](https://www.pexels.com/api/) арқылы кездейсоқ **жарқын/түрлі-түсті
(vibrant)** 16:9 stock footage (neon cafe, colorful city night, cozy lounge, т.б.) іздеп,
автоматты жүктеп алады. Pexels лицензиясы commercial/monetized use-ке толық еркін,
атрибуция керек емес.

**Баптау:**
1. https://www.pexels.com/api/ — тегін тіркеліп, API кілт алыңыз (AITechShorts-тың
   кілтін қайта пайдалануға болады — лимит 20 000/ай ортақ жеткілікті, бұл бот күніне
   1 рет қана сұрайды).
2. `.env`-ге `PEXELS_API_KEY=...` қосыңыз.
3. Кілт болмаса — код автоматты `backgrounds/` папкасындағы локал loop видеоға ауысады,
   сондықтан 1 сақтық landscape видео қосып қою ұсынылады.

## 6. Монетизация туралы маңызды ескерту

- YouTube Audio Library + Pexels қолданғанда **copyright claim тәуекелі жоқтың қасы**.
- Бірақ YouTube Partner Program-ге (монетизация) өту үшін арна **1000 жазылушы + 4000
  сағат watch time (12 айда)** шегіне жетуі керек — бұл арнаның өсуіне байланысты, бот
  бұл шектерге автоматты жеткізбейді, тек контентті тұрақты (күнде 1 видео) шығарады.
- Видео ұзақ (70-110 мин) болғандықтан, финалды файл 1-3GB болуы мүмкін — бірінші
  жергілікті сынауда upload уақытын өлшеп алыңыз.

## 7. Тексеру реті

1. `.env.example`-ды `.env` етіп көшіріп, нақты кілттермен толтырыңыз.
2. `ffmpeg`/`ffprobe`-дің жергілікті компьютерде орнатылғанын тексеріңіз (`ffmpeg -version`).
3. `pip install -r requirements.txt`
4. Жергілікті сынау (жүктеместен): `python -c "from jazz_video_gen import generate_video; generate_video(skip_upload=True)"`
5. `final_jazz_mix.mp4`-ты тексеріңіз (ұзақтық 70-110 мин аралығында ма, аудио үзіліссіз бе,
   фон loop көрінбей ме).
6. Нақты жүктеуді бір рет қолмен сынаңыз: `python jazz_video_gen.py`
7. Барлығы жұмыс істесе, GitHub Actions-та `workflow_dispatch` арқылы бір рет қолмен
   іске қосып тексеріңіз (уақытын өлшеп, қажет болса `timeout-minutes`-ті түзетіңіз).
8. Содан кейін ғана cron кестесіне сеніп қалдырыңыз.
