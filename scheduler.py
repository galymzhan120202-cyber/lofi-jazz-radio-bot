import os
import sys
import io
import schedule
import time
import logging
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
load_dotenv()

# Күніне 1 рет (UTC). AITech (03:30/09:30/15:30 UTC) және психология
# ботымен (03:00/09:00/15:00 UTC) соқтықпас үшін таңдалды. Қазақстан UTC+5:
POST_TIME = os.getenv('POST_TIME', '06:00')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from jazz_video_gen import generate_video, send_telegram

def job():
    logger.info("⏰ Jazz жүктеу басталды...")
    send_telegram("⏰ <b>Velvet Jazz Lounge жүктеу басталды</b>")
    try:
        generate_video()
        logger.info("✅ Jazz жүктеу сәтті аяқталды")
    except Exception as e:
        logger.error(f"❌ Jazz жүктеу сәтсіз: {e}")

schedule.every().day.at(POST_TIME).do(job)

kz_time = f"{(int(POST_TIME.split(':')[0]) + 5) % 24:02d}:{POST_TIME.split(':')[1]}"
logger.info(f"🚀 Jazz Scheduler іске қосылды — күнде 1 видео, {POST_TIME} UTC ({kz_time} KZ)")
logger.info("   Тоқтату үшін Ctrl+C")
send_telegram(
    f"🚀 <b>Velvet Jazz Lounge Scheduler іске қосылды</b>\n"
    f"📅 Күнде <b>1 видео</b>\n"
    f"🕐 Уақыты (KZ): <b>{kz_time}</b>"
)

while True:
    schedule.run_pending()
    time.sleep(30)
