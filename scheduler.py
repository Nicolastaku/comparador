"""
scheduler.py
Ejecuta el scraper automáticamente 1 vez al día.
"""
import schedule
import time
from datetime import datetime

from scraper import actualizar_todo
from database import init_db


HORA_EJECUCION = "03:00"


def job():
    inicio = datetime.now()
    print(f"\n{'='*60}")
    print(f"⏰ [{inicio:%Y-%m-%d %H:%M:%S}] Iniciando scraping diario")
    print(f"{'='*60}")

    try:
        actualizar_todo()
        duracion = (datetime.now() - inicio).total_seconds()
        print(f"✅ Completado en {duracion:.1f} segundos")
    except Exception as e:
        print(f"❌ Error fatal: {e}")


def main():
    init_db()

    schedule.every().day.at(HORA_EJECUCION).do(job)

    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║  ⏳ Scheduler activo                                     ║
    ║  📅 Próxima ejecución: todos los días a las {HORA_EJECUCION}  ║
    ║  💡 Ctrl+C para detener                                  ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    print("▶️  Ejecutando primera actualización de prueba...\n")
    job()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()