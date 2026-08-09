import os
import sys
import io
import json
import glob
import random
import shutil
import logging
import subprocess
import time
import traceback

import requests
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.http
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

from thumbnail_gen import make_thumbnail, HOOK_LINES

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

# --- ПАРАМЕТРЛЕР ---
# Абсолютты жолға айналдыру міндетті: ffmpeg concat demuxer салыстырмалы
# файл жолдарын list файлдың өз орналасуына қатысты шешеді (CWD-ге емес),
# сондықтан BASE_DIR=. секілді салыстырмалы мән қосарланған жол қатесін тудырады.
base_dir = os.path.abspath(os.getenv('BASE_DIR', os.path.dirname(os.path.abspath(__file__))))
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')
TELEGRAM_NOTIFY_TOKEN = os.getenv('TELEGRAM_NOTIFY_TOKEN', '')
TELEGRAM_NOTIFY_CHAT_ID = os.getenv('TELEGRAM_NOTIFY_CHAT_ID', '')

JAZZ_MIN_MINUTES = int(os.getenv('JAZZ_MIN_MINUTES', '70'))
JAZZ_MAX_MINUTES = int(os.getenv('JAZZ_MAX_MINUTES', '110'))

YOUTUBE_CATEGORY_ID = os.getenv('YOUTUBE_CATEGORY_ID', '10')  # 10 = Music
YOUTUBE_PRIVACY_STATUS = os.getenv('YOUTUBE_PRIVACY_STATUS', 'public')
YOUTUBE_MADE_FOR_KIDS = os.getenv('YOUTUBE_MADE_FOR_KIDS', 'false').lower() == 'true'

MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '2'))

MUSIC_DIR = os.path.join(base_dir, 'music')
BACKGROUNDS_DIR = os.path.join(base_dir, 'backgrounds')
TEMP_DIR = os.path.join(base_dir, 'temp_jazz')
TRACK_INFO_FILE = os.path.join(MUSIC_DIR, 'track_info.json')
FINAL_OUTPUT = os.path.join(base_dir, 'final_jazz_mix.mp4')
THUMBNAIL_OUTPUT = os.path.join(base_dir, 'final_thumbnail.png')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(base_dir, 'debug.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MUSIC_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.ogg', '.aac')


def retry_with_backoff(func, max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY):
    """Функцияны қайта сынау (exponential backoff)"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logger.warning(f"⚠️ Сәтсіз (әрекет {attempt + 1}/{max_retries}): {str(e)[:150]}")
                logger.info(f"⏳ {wait_time} сек. күте тұр...")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ {max_retries} әрекеттен кейін сәтсіз")
                raise


def send_telegram(message: str):
    """Telegram хабарламасы жіберу"""
    if not TELEGRAM_NOTIFY_TOKEN or not TELEGRAM_NOTIFY_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_NOTIFY_TOKEN}/sendMessage"
        requests.post(
            url,
            json={"chat_id": TELEGRAM_NOTIFY_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception:
        pass


def run_ffmpeg(args, description):
    """ffmpeg/ffprobe командасын subprocess арқылы орындау, қатені логтау."""
    cmd = [args[0]] + ['-y'] + args[1:] if args[0] == 'ffmpeg' else args
    logger.info(f"  ⚙️ {description}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if result.returncode != 0:
        raise RuntimeError(f"{description} сәтсіз: {result.stderr[-800:]}")
    return result


def get_duration_sec(path):
    """ffprobe арқылы медиа файлдың ұзақтығын секундпен алу."""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', path],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"ffprobe ұзақтықты аныта алмады: {path}")
    return float(result.stdout.strip())


def ensure_directories_exist():
    """Қажетті папқаларды тексеру."""
    for directory in (BACKGROUNDS_DIR, MUSIC_DIR):
        if not os.path.exists(directory):
            raise FileNotFoundError(f"❌ Папқа жоқ: {directory}")

    music_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(MUSIC_EXTENSIONS)]
    if not music_files:
        raise FileNotFoundError(
            "❌ music/ бос — YouTube Audio Library-ден 'Jazz' genre фильтрімен "
            "кемінде 25-30 трек жүктеп қою керек (SETUP.md-ды қараңыз)"
        )

    bg_files = [f for f in os.listdir(BACKGROUNDS_DIR) if not f.startswith('_pexels')]
    if not bg_files and not PEXELS_API_KEY:
        raise FileNotFoundError("❌ backgrounds/ бос және PEXELS_API_KEY орнатылмаған")

    os.makedirs(TEMP_DIR, exist_ok=True)
    logger.info("✓ Барлық папқалар дайын")


def load_track_info():
    """music/track_info.json файлынан трек метаданные (атрибуция/лицензия) оқу.
    Файл жоқ болса — бос dict қайтарады (атрибуциясыз жалғастыруға болады)."""
    if not os.path.exists(TRACK_INFO_FILE):
        return {}
    try:
        with open(TRACK_INFO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ track_info.json оқылмады: {e}")
        return {}


def build_jazz_playlist(target_sec):
    """music/ папкасындағы локал jazz треконан (YouTube Audio Library-ден жүктелген)
    target_sec ұзақтыққа жететін треклист құрастыру. Трек қайталанбауға тырысады,
    пул жеткіліксіз болса ғана (жиынтық ұзақтық target_sec-тен аз) қайталауға рұқсат
    беріп, warning логтайды."""
    track_info = load_track_info()

    files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(MUSIC_EXTENSIONS)]
    pool = []
    total_pool_duration = 0.0
    for filename in files:
        path = os.path.join(MUSIC_DIR, filename)
        try:
            duration = get_duration_sec(path)
        except Exception as e:
            logger.warning(f"⚠️ Ұзақтық анықталмады, өткізіп жіберілді: {filename} ({e})")
            continue
        meta = track_info.get(filename, {})
        pool.append({
            "path": path,
            "filename": filename,
            "duration": duration,
            "title": meta.get("title", os.path.splitext(filename)[0]),
            "creator": meta.get("creator"),
            "attribution_required": meta.get("attribution_required", False),
            "attribution_text": meta.get("attribution_text"),
        })
        total_pool_duration += duration

    if not pool:
        raise RuntimeError("music/ ішінде ұзақтығы анықталатын трек табылмады")

    if total_pool_duration < target_sec:
        logger.warning(
            f"⚠️ music/ пулы тым кіші ({total_pool_duration/60:.1f} мин < "
            f"қажетті {target_sec/60:.1f} мин) — треk қайталанады. "
            f"SETUP.md бойынша көбірек трек қосу ұсынылады."
        )

    selected = []
    cumulative = 0.0
    remaining = list(pool)
    random.shuffle(remaining)

    while cumulative < target_sec:
        if not remaining:
            remaining = list(pool)
            random.shuffle(remaining)
        track = remaining.pop()
        selected.append(track)
        cumulative += track["duration"]

    logger.info(
        f"✓ Треклист дайын: {len(selected)} трек, жинақы ұзақтық "
        f"{cumulative/60:.1f} мин (мақсат: {target_sec/60:.1f} мин)"
    )
    return selected


def build_combined_audio(selected_tracks, target_sec):
    """Таңдалған треконы бірдей форматқа (AAC 44.1kHz stereo) келтіріп,
    ffmpeg concat demuxer арқылы бір файлға склейкалап, target_sec-ке дәл қиып алу."""
    normalized_paths = []
    for i, track in enumerate(selected_tracks):
        norm_path = os.path.join(TEMP_DIR, f"norm_{i:03d}.m4a")
        run_ffmpeg(
            ['ffmpeg', '-i', track["path"], '-vn', '-ar', '44100', '-ac', '2',
             '-c:a', 'aac', '-b:a', '192k', norm_path],
            f"Нормализация: {track['filename']}"
        )
        normalized_paths.append(norm_path)

    concat_list_path = os.path.join(TEMP_DIR, 'concat_list.txt')
    with open(concat_list_path, 'w', encoding='utf-8') as f:
        for p in normalized_paths:
            safe_path = p.replace('\\', '/')
            f.write(f"file '{safe_path}'\n")

    combined_path = os.path.join(TEMP_DIR, 'combined.m4a')
    run_ffmpeg(
        ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_list_path,
         '-t', str(target_sec), '-c', 'copy', combined_path],
        "Аудио склейка + қию"
    )
    return combined_path


VIVID_BG_QUERIES = [
    "vibrant neon cafe night", "colorful city lights night rain",
    "bright cozy coffee shop aesthetic", "colorful vinyl record neon lights",
    "aesthetic vibrant lounge bar", "neon lights rain window colorful",
    "colorful jazz bar night", "vibrant city skyline night lights",
]


def fetch_pexels_loop_bg():
    """Pexels API арқылы жарқын/түрлі-түсті 16:9 (landscape) loop-қа жарамды
    видео жүктеп алу. Кілт жоқ/сәтсіз болса — None (локал fallback үшін)."""
    if not PEXELS_API_KEY:
        return None

    query = random.choice(VIVID_BG_QUERIES)
    try:
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "orientation": "landscape", "per_page": 15},
            timeout=15
        )
        response.raise_for_status()
        videos = response.json().get("videos", [])
        if not videos:
            logger.warning(f"⚠️ Pexels: '{query}' бойынша видео табылмады")
            return None

        video_data = random.choice(videos)
        candidates = [
            vf for vf in video_data.get("video_files", [])
            if vf.get("width", 0) > vf.get("height", 0)
            and 1280 <= vf.get("width", 0) <= 1920
        ]
        if not candidates:
            candidates = [
                vf for vf in video_data.get("video_files", [])
                if vf.get("width", 0) > vf.get("height", 0) and vf.get("width", 0) >= 854
            ]
        if not candidates:
            return None

        candidates.sort(key=lambda vf: vf["width"], reverse=True)
        video_file = candidates[0]

        dest = os.path.join(BACKGROUNDS_DIR, "_pexels_temp.mp4")
        dl_response = requests.get(video_file["link"], stream=True, timeout=60)
        dl_response.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in dl_response.iter_content(chunk_size=1024 * 256):
                f.write(chunk)

        if os.path.getsize(dest) < 10_000:
            raise Exception("Жүктелген видео тым кіші")

        logger.info(f"✓ Pexels-тен фон видео жүктелді (сұрау: '{query}')")
        return dest

    except Exception as e:
        logger.warning(f"⚠️ Pexels қатесі, локал fallback қолданылады: {str(e)[:150]}")
        return None


def get_background_video():
    bg_path = fetch_pexels_loop_bg()
    if bg_path:
        return bg_path

    bg_files = [
        f for f in os.listdir(BACKGROUNDS_DIR)
        if f.lower().endswith(('.mp4', '.mov')) and not f.startswith('_pexels')
    ]
    if not bg_files:
        raise FileNotFoundError("Фон видео жоқ (Pexels де, локал да)")
    return os.path.join(BACKGROUNDS_DIR, random.choice(bg_files))


MOODS = [
    "Relaxing", "Cozy", "Rainy Night", "Late Night", "Sunday Morning",
    "Deep Focus", "Study & Chill", "Midnight", "Warm", "Peaceful",
]

TITLE_TEMPLATES = [
    "{mood} Jazz for Studying & Relaxation",
    "{mood} Jazz Lounge — Non-Stop Smooth Jazz",
    "Smooth Jazz Piano — {mood} Ambience for Work & Sleep",
    "{mood} Jazz Cafe — Chill Background Music",
]

# Ең жоғары іздеу көлемді 3 hashtag — YouTube сипаттаманың алғашқы 3 hashtag-ын
# видео тақырыбының үстінде басылатын chip ретінде көрсетеді, сондықтан бұлар
# әрдайым ең күшті/кең тақырыптық болуы керек (тұрақты, айналмайды).
ANCHOR_HASHTAGS = ["#jazz", "#relaxingmusic", "#studymusic"]

HASHTAG_POOL = [
    "#lofijazz", "#smoothjazz", "#jazzcafe",
    "#chilljazz", "#focusmusic", "#jazzmusic",
    "#backgroundmusic", "#jazzpiano", "#loungejazz",
    "#jazznoir", "#coffeeshopmusic", "#rainyjazz", "#jazzvibes",
    "#ambientmusic", "#jazzbar", "#sleepmusic", "#relaxingjazz",
    "#worklofi", "#eveningjazz", "#jazzlounge", "#cozyjazz",
]

# YouTube-тың жасырын tags[] өрісіне арналған көп сөзді іздеу фразалары —
# hashtag-тардан бөлек, себебі адамдар іздеу жолағына бір сөз емес, тіркес
# теретінін ескереді ("jazz music for studying" секілді).
SEO_KEYWORD_PHRASES = [
    "jazz music", "relaxing jazz music", "jazz music for studying",
    "jazz music for work", "smooth jazz playlist", "lofi jazz mix",
    "jazz cafe music", "coffee shop jazz music", "sleep music jazz",
    "jazz piano music", "jazz for sleeping", "background jazz music",
    "study jazz playlist", "jazz lounge music", "rainy day jazz",
    "cozy jazz music", "jazz instrumental music", "long jazz playlist",
]


def pick_rotating_tags(count=6):
    """ANCHOR_HASHTAGS әрдайым бірінші (YouTube олардан chip көрсетеді),
    қалғаны пулдан кездейсоқ таңдалады."""
    extra = random.sample(HASHTAG_POOL, min(count, len(HASHTAG_POOL)))
    return ' '.join(ANCHOR_HASHTAGS + extra)


PLAYLIST_THEMES = {
    "Deep Focus": "Focus & Study Jazz",
    "Study & Chill": "Focus & Study Jazz",
    "Late Night": "Late Night Jazz Lounge",
    "Midnight": "Late Night Jazz Lounge",
    "Rainy Night": "Late Night Jazz Lounge",
    "Relaxing": "Relaxing Jazz Lounge",
    "Peaceful": "Relaxing Jazz Lounge",
    "Warm": "Relaxing Jazz Lounge",
    "Cozy": "Relaxing Jazz Lounge",
    "Sunday Morning": "Morning Jazz Cafe",
}
MASTER_PLAYLIST_TITLE = "Velvet Jazz Lounge — All Mixes"


def build_title_and_description(selected_tracks):
    mood = random.choice(MOODS)
    title = random.choice(TITLE_TEMPLATES).format(mood=mood)[:100]

    tracklist_lines = []
    attribution_lines = []
    seen_titles = set()
    for track in selected_tracks:
        label = track["title"]
        if label in seen_titles:
            continue
        seen_titles.add(label)
        creator = track.get("creator")
        line = f'"{label}"' + (f" — {creator}" if creator else "")
        tracklist_lines.append(line)
        if track.get("attribution_required") and track.get("attribution_text"):
            attribution_lines.append(track["attribution_text"])

    hashtags = pick_rotating_tags()
    divider = "─" * 28

    # Бірінші абзацта негізгі кілт сөздерді табиғи сөйлеммен қайталау — YouTube
    # іздеу индексі сипаттама мәтінін де оқиды, тек hashtag-тарды емес.
    seo_intro = (
        f"A {mood.lower()} smooth jazz mix — the perfect jazz playlist for studying, "
        f"working, relaxing or falling asleep. A cozy jazz lounge blend of piano, "
        f"saxophone and lounge jazz to help you focus or unwind."
    )

    description_parts = [
        f"🎷 {title}",
        f"\n{seo_intro}\n",
        f"{divider}",
        "🎶 TRACKLIST",
        f"{divider}",
        "\n".join(f"{i+1}. {line}" for i, line in enumerate(tracklist_lines[:40])),
    ]
    if attribution_lines:
        description_parts.append(f"\n{divider}\nAttribution\n{divider}\n" + "\n".join(attribution_lines))
    description_parts.append(
        f"\n{divider}\n📻 VELVET JAZZ LOUNGE\n{divider}\n"
        "A new smooth jazz mix, every single day. 🔔 Subscribe and turn on "
        "notifications so you never miss a session."
    )
    description_parts.append(f"\n{hashtags}")

    description = "\n".join(description_parts)

    # tags[] — hashtag сөздері + көп сөзді SEO фразалар (адамдар нақ осылай іздейді).
    seo_tags = random.sample(SEO_KEYWORD_PHRASES, min(8, len(SEO_KEYWORD_PHRASES)))
    tags = [t.lstrip('#') for t in hashtags.split()] + seo_tags + ["velvet jazz lounge"]

    return title, description, tags, mood


def mux_final_video(bg_path, combined_audio_path, target_sec):
    run_ffmpeg(
        ['ffmpeg', '-fflags', '+genpts', '-stream_loop', '-1', '-i', bg_path,
         '-i', combined_audio_path,
         '-map', '0:v:0', '-map', '1:a:0',
         '-c:v', 'copy', '-c:a', 'copy',
         '-t', str(target_sec), '-shortest', FINAL_OUTPUT],
        "Финалды видео мукстеу (loop + аудио)"
    )
    return FINAL_OUTPUT


def get_or_create_playlist(youtube, title):
    """Атауы бойынша каналдағы плейлистті табады, жоқ болса жасайды.
    Плейлисттер жанрлық іздеуде ("jazz playlist") өз алдына индекстеледі
    және session watch time-ды арттырады — жаңа арнаға алгоритмдік
    трафик тартудың ең тез жолдарының бірі."""
    request = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
    while request is not None:
        response = request.execute()
        for item in response.get("items", []):
            if item["snippet"]["title"] == title:
                return item["id"]
        request = youtube.playlists().list_next(request, response)

    created = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": f"{title} — Velvet Jazz Lounge smooth jazz mixes.",
            },
            "status": {"privacyStatus": YOUTUBE_PRIVACY_STATUS},
        },
    ).execute()
    return created["id"]


def add_video_to_playlists(youtube, video_id, mood):
    """Видеоны mood-ына сай тақырыптық плейлистке және жалпы master
    плейлистке қосады. Плейлист операциялары upload-ты бұзбауы үшін
    әр плейлист бөлек try/except-пен қоршалған."""
    titles = [MASTER_PLAYLIST_TITLE]
    theme = PLAYLIST_THEMES.get(mood)
    if theme:
        titles.append(theme)

    for playlist_title in titles:
        try:
            def add_one(playlist_title=playlist_title):
                playlist_id = get_or_create_playlist(youtube, playlist_title)
                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {"kind": "youtube#video", "videoId": video_id},
                        }
                    },
                ).execute()

            # Жаңа жүктелген видеоны бірінші playlistItems.insert шақыруы кейде
            # HttpError 409 "The operation was aborted" қайтарады — YouTube backend
            # видеоны әлі толық таратып үлгермегендіктен. Қысқа retry жеткілікті.
            retry_with_backoff(add_one, max_retries=3, retry_delay=2)
            logger.info(f"✓ Плейлистке қосылды: {playlist_title}")
        except Exception as e:
            logger.warning(f"⚠️ Плейлистке қосу сәтсіз ({playlist_title}): {str(e)[:150]}")


def upload_to_youtube(video_path, title, description, tags=None, thumbnail_path=None, mood=None):
    logger.info("📤 YouTube-ке жүктеу басталуда...")

    # youtube.upload жеткіліксіз — thumbnails().set() кеңейтілген
    # "https://www.googleapis.com/auth/youtube" scope-ын талап етеді.
    scopes = ["https://www.googleapis.com/auth/youtube"]
    client_file = os.path.join(base_dir, "client_secrets.json")
    token_file = os.path.join(base_dir, "youtube_token.json")

    credentials = None

    try:
        if os.path.exists(token_file):
            try:
                credentials = Credentials.from_authorized_user_file(token_file, scopes)
                if credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                    with open(token_file, 'w') as f:
                        f.write(credentials.to_json())
                logger.info("✓ Сохраненные учетные данные загружены")
            except Exception as e:
                logger.warning(f"⚠️ Токен мәселесі: {e}")
                credentials = None

        if credentials is None:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                client_file, scopes
            )
            credentials = flow.run_local_server(
                port=0,
                open_browser=True,
                authorization_prompt_message='Браузерде OAuth логинін орындаңыз: {url}',
                success_message='✓ Аутентификация сәтті! Терезесін жабыңыз.'
            )
            with open(token_file, 'w') as f:
                f.write(credentials.to_json())
            logger.info("✓ Жаңа OAuth токены сақталды")

        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

        request_body = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": YOUTUBE_CATEGORY_ID,
                "tags": tags or ["jazz", "lofi jazz", "relaxing music"],
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en"
            },
            "status": {
                "privacyStatus": YOUTUBE_PRIVACY_STATUS,
                "selfDeclaredMadeForKids": YOUTUBE_MADE_FOR_KIDS
            }
        }

        logger.info(f"📤 Файл жүктелуде: {os.path.basename(video_path)}")

        media = googleapiclient.http.MediaFileUpload(
            video_path,
            chunksize=1024 * 1024 * 8,
            resumable=True
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info(f"  Прогресс: {progress}%")

        video_id = response['id']
        logger.info("\n✅ ЖЕҢІС! Видео YouTube-та жүктелді!")
        logger.info(f"   ID: {video_id}")
        logger.info(f"   URL: https://youtube.com/watch?v={video_id}")

        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=googleapiclient.http.MediaFileUpload(thumbnail_path)
                ).execute()
                logger.info("✓ Custom thumbnail орнатылды")
            except Exception as e:
                # Телефон нөмірі расталмаған арналарда thumbnails().set() 403 қайтарады —
                # видео жүктелуіне кедергі болмауы үшін тек warning ретінде логтаймыз.
                logger.warning(f"⚠️ Thumbnail орнатылмады (арна телефонмен расталған ба тексеріңіз): {str(e)[:200]}")

        if mood:
            add_video_to_playlists(youtube, video_id, mood)

    except Exception as e:
        logger.error(f"❌ Жүктеу қатесі: {e}")
        raise


def cleanup_temp_files():
    """Уақытша файлдарды өшіру."""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    for temp_file in glob.glob(os.path.join(BACKGROUNDS_DIR, "_pexels_temp.mp4")):
        try:
            os.remove(temp_file)
        except Exception:
            pass


def generate_video(skip_upload: bool = False):
    try:
        logger.info("🎬 Jazz видео құру процессі басталды")

        ensure_directories_exist()
        cleanup_temp_files()
        os.makedirs(TEMP_DIR, exist_ok=True)

        target_minutes = random.randint(JAZZ_MIN_MINUTES, JAZZ_MAX_MINUTES)
        target_sec = target_minutes * 60
        logger.info(f"🎯 Мақсатты ұзақтық: {target_minutes} мин")

        selected_tracks = build_jazz_playlist(target_sec)

        logger.info("🎵 Аудио құрастырылуда...")
        combined_audio_path = retry_with_backoff(
            lambda: build_combined_audio(selected_tracks, target_sec)
        )

        logger.info("🖼️ Фон видео алынуда...")
        bg_path = retry_with_backoff(get_background_video)

        title, description, tags, mood = build_title_and_description(selected_tracks)
        logger.info(f"🏷️ Тақырып: {title}")

        logger.info("🖼️ Thumbnail жасалуда...")
        try:
            hook_text = random.choice(HOOK_LINES)
            make_thumbnail(hook_text, target_minutes, THUMBNAIL_OUTPUT)
            logger.info(f"✓ Thumbnail дайын: {THUMBNAIL_OUTPUT}")
        except Exception as e:
            logger.warning(f"⚠️ Thumbnail жасалмады: {str(e)[:150]}")

        logger.info("⏳ Финалды видео мукстелуде...")
        final_path = retry_with_backoff(lambda: mux_final_video(bg_path, combined_audio_path, target_sec))
        logger.info(f"✓ Видео дайын: {final_path}")

        if not skip_upload:
            thumb = THUMBNAIL_OUTPUT if os.path.exists(THUMBNAIL_OUTPUT) else None
            retry_with_backoff(lambda: upload_to_youtube(final_path, title, description, tags, thumb, mood))
            send_telegram(
                f"✅ <b>Жаңа Jazz видео жүктелді!</b>\n"
                f"📌 <b>Тақырып:</b> {title}\n"
                f"⏱️ <b>Ұзақтық:</b> {target_minutes} мин"
            )
        else:
            logger.info("✓ Видео сақталды (жүктеу өтіп кетті)")

        cleanup_temp_files()

    except Exception as e:
        logger.error(f"❌ Қате: {e}")
        logger.debug(traceback.format_exc())
        send_telegram(f"❌ <b>Jazz видео жасауда қате шықты!</b>\n<code>{str(e)[:300]}</code>")
        raise


if __name__ == "__main__":
    try:
        generate_video()
    except Exception as e:
        logger.error(f"Программа сәтсіз аяқталды: {e}")
        sys.exit(1)
