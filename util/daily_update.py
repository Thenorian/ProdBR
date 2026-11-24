"""
Atualização diária dos dados oficiais (NCM, IPI, II e tabela do IBPT), dentro do próprio app, sem cron no servidor.

Roda numa linha de execução em segundo plano: espera um minuto depois da subida
(para não atrasar o início) e depois repete a cada 24 horas. Se o site do governo
estiver fora do ar, só registra o erro e tenta de novo no dia seguinte.

Desligar: NCM_AUTO_UPDATE=false no .env (os testes desligam).
"""
import os
import threading
import time

from database.fiscal import FiscalDB
from util.data_util import DataUtil
from util.ibpt_data import update_all_states as update_ibpt_tables
from util.official_data import download_federal_rates, download_ncm_table

FIRST_RUN_DELAY_IN_SECONDS = 60
SECONDS_BETWEEN_UPDATES = 24 * 60 * 60


def start_daily_official_update():
    if os.getenv("NCM_AUTO_UPDATE", "true").strip().lower() in ("false", "0", "nao", "não", "no"):
        return

    threading.Thread(target=update_every_day, name="atualizacao-oficial-diaria", daemon=True).start()


def update_every_day():
    time.sleep(FIRST_RUN_DELAY_IN_SECONDS)
    while True:
        update_official_data_now()
        time.sleep(SECONDS_BETWEEN_UPDATES)


def update_official_data_now():
    """Baixa e grava a tabela NCM, depois o IPI e o II, depois o IBPT. Uma falha não impede a outra."""
    try:
        ok, summary = DataUtil().import_ncm_content(download_ncm_table(), "Siscomex (download diário)")
        if not ok:
            print(f"[OFICIAL] NCM: erro ao gravar: {summary}")
        elif summary.get("already_imported"):
            print(f"[OFICIAL] NCM: sem novidade ({summary['version_label']})")
        else:
            print(f"[OFICIAL] NCM: {summary['saved']} códigos, {summary['no_longer_in_force']} saíram de vigor")
    except Exception as error:
        print(f"[OFICIAL] NCM: não foi possível baixar do Siscomex: {error}")

    try:
        ok, totals = FiscalDB().apply_official_rates(download_federal_rates())
        if ok:
            print(f"[OFICIAL] IPI/II: {totals['created']} novas, {totals['changed']} alteradas, {totals['unchanged']} iguais")
        else:
            print(f"[OFICIAL] IPI/II: erro ao gravar: {totals}")
    except Exception as error:
        print(f"[OFICIAL] IPI/II: não foi possível baixar a TIPI ou a TEC: {error}")

    update_ibpt_tables()
