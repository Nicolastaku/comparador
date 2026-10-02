"""
scheduler.py
Ejecuta scraper + verificación de alertas 1 vez al día.
"""
import os
import time
import schedule
from datetime import datetime

from scraper import actualizar_todo
from database import init_db


HORA = os.getenv("SCRAPER_HORA", "03:00")


def job():
    inicio = datetime.now()
    print(f"\n{'='*60}")
    print(f"⏰ [{inicio:%Y-%m-%d %H:%M:%S}] Scraping diario")
    print(f"{'='*60}")
    try:
        actualizar_todo(descubrir=True, verificar_alertas_al_final=True)
        duracion = (datetime.now() - inicio).total_seconds()
        print(f"✅ Completado en {duracion:.1f}s")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    init_db()
    schedule.every().day.at(HORA).do(job)
    print(f"⏳ Scheduler activo. Corre a las {HORA} todos los días.")
    job()  # Correr una vez al iniciar
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()