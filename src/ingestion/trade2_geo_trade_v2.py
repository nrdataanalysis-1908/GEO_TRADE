"""
GEO_TRADE | Extracao MT5 -> SQLite
Versao aprimorada para validacao local.

Requisitos:
    pip install MetaTrader5 colorama

Execucao:
    python trade2.py
    python trade2.py --date 2026-11-01
    python trade2.py --symbols EURUSD GBPUSD
    python trade2.py --no-open-db
"""

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import unicodedata
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

try:
    import MetaTrader5 as mt5
except ImportError:  # MT5 is only needed by the live terminal entry point.
    mt5 = None

from colorama import Fore, init


# ============================================================
# IDENTIDADE E CONFIGURACAO
# ============================================================

init(autoreset=True)

AZUL = Fore.LIGHTBLUE_EX
CIANO = Fore.LIGHTCYAN_EX
AMARELO = Fore.LIGHTYELLOW_EX
VERMELHO = Fore.LIGHTRED_EX
BRANCO = Fore.LIGHTWHITE_EX
VERDE = Fore.LIGHTGREEN_EX

MT5_PATH_PADRAO = r"C:\Program Files\MetaTrader 5\terminal64.exe"
PASTA_BASE_PADRAO = Path.home() / "Downloads"
DB_PATH_PADRAO = PASTA_BASE_PADRAO / "geo_trade_completo.db"

TIMEFRAME = getattr(mt5, "TIMEFRAME_M1", None)
TIMEFRAME_NOME = "M1"
FUSO_BRASILIA = timezone(timedelta(hours=-3), name="America/Sao_Paulo")
PAUSA_ATIVO = 0.015
SQLITE_INTEGER_MAX = (1 << 63) - 1


def _has_control_characters(value):
    return any(unicodedata.category(character) == "Cc" for character in value)


# ============================================================
# ARGUMENTOS
# ============================================================

def validar_simbolos(symbols):
    """Validate explicit MT5 symbol arguments and reject ambiguous duplicates."""
    if symbols is None:
        return None
    if not isinstance(symbols, (list, tuple)) or not symbols:
        raise ValueError("symbols must be a non-empty list when provided")
    normalized = []
    seen = set()
    for symbol in symbols:
        if (
            not isinstance(symbol, str)
            or not symbol.strip()
            or symbol != symbol.strip()
            or _has_control_characters(symbol)
        ):
            raise ValueError(
                "each symbol must be a non-empty trimmed string without control characters"
            )
        if symbol in seen:
            raise ValueError(f"duplicate symbol argument: {symbol}")
        seen.add(symbol)
        normalized.append(symbol)
    return normalized


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extrai candles M1 do MetaTrader 5 e grava em SQLite."
    )
    parser.add_argument(
        "--date",
        dest="data_alvo",
        help="Data local a extrair no formato YYYY-MM-DD. Padrao: dia anterior."
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Lista opcional de ativos. Sem este argumento, consulta todos os ativos do MT5."
    )
    parser.add_argument(
        "--terminal-path",
        default=MT5_PATH_PADRAO,
        help="Caminho do terminal64.exe."
    )
    parser.add_argument(
        "--db-path",
        default=str(DB_PATH_PADRAO),
        help="Caminho do arquivo SQLite."
    )
    parser.add_argument(
        "--no-open-db",
        action="store_true",
        help="Nao abre o DB Browser automaticamente ao finalizar."
    )
    return parser.parse_args()


# ============================================================
# DATA E FUSO HORARIO
# ============================================================

def obter_intervalo_utc(data_informada=None):
    """
    Interpreta a data como dia civil de Brasilia e converte os limites
    para UTC, formato esperado pelas funcoes de historico do MT5.
    """
    if data_informada is not None:
        if not isinstance(data_informada, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data_informada):
            raise ValueError("date must use YYYY-MM-DD")
        data_local = date.fromisoformat(data_informada)
    else:
        data_local = datetime.now(FUSO_BRASILIA).date() - timedelta(days=1)

    inicio_local = datetime.combine(
        data_local, datetime_time.min, tzinfo=FUSO_BRASILIA
    )
    try:
        fim_local = inicio_local + timedelta(days=1)
    except OverflowError as exc:
        raise ValueError("date must allow an exclusive next-day boundary") from exc

    return (
        data_local,
        inicio_local.astimezone(timezone.utc),
        fim_local.astimezone(timezone.utc),
    )


# ============================================================
# BANCO SQLITE
# ============================================================

def preparar_banco(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ativos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE,
            description TEXT,
            path TEXT,
            currency_base TEXT,
            currency_profit TEXT,
            currency_margin TEXT,
            digits INTEGER,
            point REAL,
            trade_tick_size REAL,
            trade_tick_value REAL,
            volume_min REAL,
            volume_max REAL,
            volume_step REAL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            timestamp_brasilia TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            tick_volume INTEGER,
            spread INTEGER,
            real_volume INTEGER,
            UNIQUE(symbol, timeframe, timestamp_utc)
        );

        CREATE INDEX IF NOT EXISTS idx_candles_symbol
            ON candles(symbol);

        CREATE INDEX IF NOT EXISTS idx_candles_timestamp
            ON candles(timestamp_utc);

        CREATE INDEX IF NOT EXISTS idx_candles_symbol_time
            ON candles(symbol, timestamp_utc);
    """)
    conn.commit()
    return conn


def gravar_metadados_ativo(cursor, info):
    try:
        validar_simbolos([getattr(info, "name", None)])
    except ValueError as exc:
        raise ValueError("asset metadata requires a valid symbol") from exc
    agora = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
        INSERT INTO ativos (
            symbol, description, path, currency_base, currency_profit,
            currency_margin, digits, point, trade_tick_size,
            trade_tick_value, volume_min, volume_max, volume_step, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            description=excluded.description,
            path=excluded.path,
            currency_base=excluded.currency_base,
            currency_profit=excluded.currency_profit,
            currency_margin=excluded.currency_margin,
            digits=excluded.digits,
            point=excluded.point,
            trade_tick_size=excluded.trade_tick_size,
            trade_tick_value=excluded.trade_tick_value,
            volume_min=excluded.volume_min,
            volume_max=excluded.volume_max,
            volume_step=excluded.volume_step
    """, (
        info.name,
        getattr(info, "description", "") or "",
        getattr(info, "path", "") or "",
        getattr(info, "currency_base", "") or "",
        getattr(info, "currency_profit", "") or "",
        getattr(info, "currency_margin", "") or "",
        getattr(info, "digits", 0) or 0,
        getattr(info, "point", 0) or 0,
        getattr(info, "trade_tick_size", 0) or 0,
        getattr(info, "trade_tick_value", 0) or 0,
        getattr(info, "volume_min", 0) or 0,
        getattr(info, "volume_max", 0) or 0,
        getattr(info, "volume_step", 0) or 0,
        agora,
    ))


def validar_candle(candle):
    """Valida timestamp, OHLC e contadores antes da persistência."""
    import math

    try:
        timestamp_decimal = Decimal(str(candle["time"]))
        if (
            not timestamp_decimal.is_finite()
            or timestamp_decimal != timestamp_decimal.to_integral_value()
        ):
            return False
        timestamp = int(timestamp_decimal)
        abertura = float(candle["open"])
        maxima = float(candle["high"])
        minima = float(candle["low"])
        fechamento = float(candle["close"])
        raw_contadores = tuple(
            candle[key] for key in ("tick_volume", "spread", "real_volume")
        )
        contadores = tuple(Decimal(str(value)) for value in raw_contadores)
        if any(isinstance(candle[key], (bool, np.bool_)) for key in (
            "time", "open", "high", "low", "close",
            "tick_volume", "spread", "real_volume"
        )):
            return False
    except (KeyError, TypeError, ValueError, OverflowError, InvalidOperation):
        return False

    try:
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return False

    precos = (abertura, maxima, minima, fechamento)
    if not all(math.isfinite(valor) for valor in precos):
        return False
    if any(
        not valor.is_finite()
        or valor < 0
        or valor != valor.to_integral_value()
        or valor > SQLITE_INTEGER_MAX
        for valor in contadores
    ):
        return False
    if minima <= 0 or maxima < minima:
        return False
    if maxima < max(abertura, fechamento) or minima > min(abertura, fechamento):
        return False
    return True


def gravar_candles(cursor, symbol, rates, inicio_utc, fim_utc):
    try:
        validar_simbolos([symbol])
    except ValueError as exc:
        raise ValueError("symbol must be a valid trimmed name without control characters") from exc
    if rates is None:
        raise ValueError("rates must be an iterable of market candles")
    bounds = (inicio_utc, fim_utc)
    if any(
        not isinstance(bound, datetime)
        or bound.tzinfo is None
        or bound.utcoffset() != timedelta(0)
        for bound in bounds
    ):
        raise ValueError("inicio_utc and fim_utc must be UTC-aware datetimes")
    if fim_utc <= inicio_utc:
        raise ValueError("fim_utc must be later than inicio_utc")

    rejeitados = 0
    valid_by_timestamp = {}
    conflicting_timestamps = set()

    for candle in rates:
        if not validar_candle(candle):
            rejeitados += 1
            continue

        timestamp = int(Decimal(str(candle["time"])))
        instante_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        # O MT5 pode devolver limites inclusivos. O filtro assegura
        # que somente candles pertencentes ao dia solicitado sejam gravados.
        if not (inicio_utc <= instante_utc < fim_utc):
            continue

        market_values = (
            float(candle["open"]),
            float(candle["high"]),
            float(candle["low"]),
            float(candle["close"]),
            int(Decimal(str(candle["tick_volume"]))),
            int(Decimal(str(candle["spread"]))),
            int(Decimal(str(candle["real_volume"]))),
        )
        if timestamp in conflicting_timestamps:
            rejeitados += 1
            continue

        existing = valid_by_timestamp.get(timestamp)
        if existing is None:
            valid_by_timestamp[timestamp] = (candle, market_values)
        elif existing[1] == market_values:
            # Identical duplicate bars are collapsed deterministically.
            rejeitados += 1
        else:
            # Conflicting bars make the timestamp ambiguous; reject the
            # complete group instead of allowing INSERT OR IGNORE to pick one.
            rejeitados += 2
            del valid_by_timestamp[timestamp]
            conflicting_timestamps.add(timestamp)

    inseridos = 0
    conflitos_banco = 0
    timestamps = []
    maximas = []
    minimas = []
    for timestamp, (candle, market_values) in sorted(valid_by_timestamp.items()):
        instante_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        instante_brasilia = instante_utc.astimezone(FUSO_BRASILIA)
        timestamp_utc = instante_utc.isoformat()
        timestamp_brasilia = instante_brasilia.isoformat()

        cursor.execute("""
            INSERT OR IGNORE INTO candles (
                timestamp_utc, timestamp_brasilia, symbol, timeframe,
                open, high, low, close, tick_volume, spread, real_volume
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp_utc,
            timestamp_brasilia,
            symbol,
            TIMEFRAME_NOME,
            float(candle["open"]),
            float(candle["high"]),
            float(candle["low"]),
            float(candle["close"]),
            int(Decimal(str(candle["tick_volume"]))),
            int(Decimal(str(candle["spread"]))),
            int(Decimal(str(candle["real_volume"]))),
        ))

        if cursor.rowcount > 0:
            inseridos += 1
        else:
            persisted = cursor.execute(
                """SELECT open, high, low, close, tick_volume, spread, real_volume
                   FROM candles
                   WHERE symbol = ? AND timeframe = ? AND timestamp_utc = ?""",
                (symbol, TIMEFRAME_NOME, timestamp_utc),
            ).fetchone()
            if persisted is not None and tuple(persisted) != market_values:
                conflitos_banco += 1
                rejeitados += 1

        timestamps.append(instante_utc)
        maximas.append(float(candle["high"]))
        minimas.append(float(candle["low"]))

    return {
        "encontrados": len(timestamps),
        "inseridos": inseridos,
        "rejeitados": rejeitados,
        "conflitos_banco": conflitos_banco,
        "primeiro": min(timestamps) if timestamps else None,
        "ultimo": max(timestamps) if timestamps else None,
        "maxima": max(maximas) if maximas else None,
        "minima": min(minimas) if minimas else None,
    }


# ============================================================
# DB BROWSER
# ============================================================

def localizar_db_browser():
    caminhos = [
        r"C:\Program Files\DB Browser for SQLite\DB Browser for SQLite.exe",
        r"C:\Program Files (x86)\DB Browser for SQLite\DB Browser for SQLite.exe",
        os.path.expandvars(
            r"%LOCALAPPDATA%\Programs\DB Browser for SQLite\DB Browser for SQLite.exe"
        ),
        os.path.expandvars(
            r"%APPDATA%\DB Browser for SQLite\DB Browser for SQLite.exe"
        ),
    ]

    for caminho in caminhos:
        if Path(caminho).is_file():
            return caminho

    return shutil.which("DB Browser for SQLite.exe")


def abrir_db_browser(db_path):
    executavel = localizar_db_browser()

    if not executavel:
        print(AMARELO + "⚠ DB Browser nao localizado. O SQLite foi salvo normalmente.")
        return

    try:
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0)
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(
            [executavel, str(db_path)],
            creationflags=creationflags
        )
        print(VERDE + "✓ DB Browser aberto.")
    except Exception as erro:
        print(AMARELO + f"⚠ Nao foi possivel abrir o DB Browser: {erro}")


# ============================================================
# VALIDACAO E RELATORIO
# ============================================================

def mostrar_validacao(conn, data_alvo):
    cursor = conn.cursor()

    total = cursor.execute(
        "SELECT COUNT(*) FROM candles"
    ).fetchone()[0]

    ativos = cursor.execute(
        "SELECT COUNT(DISTINCT symbol) FROM candles"
    ).fetchone()[0]

    periodo = cursor.execute("""
        SELECT MIN(timestamp_brasilia), MAX(timestamp_brasilia)
        FROM candles
    """).fetchone()

    top = cursor.execute("""
        SELECT symbol, COUNT(*) AS quantidade,
               MIN(low) AS minima, MAX(high) AS maxima,
               MIN(timestamp_brasilia), MAX(timestamp_brasilia)
        FROM candles
        GROUP BY symbol
        ORDER BY quantidade DESC
        LIMIT 10
    """).fetchall()

    print()
    print(AZUL + "═" * 80)
    print(AZUL + " VALIDACAO DO SQLITE ")
    print(AZUL + "═" * 80)
    print(CIANO + f"  Data solicitada       : {data_alvo:%d/%m/%Y}")
    print(CIANO + f"  Ativos com candles    : {ativos}")
    print(CIANO + f"  Candles acumulados    : {total:,}")

    if periodo and periodo[0]:
        print(CIANO + f"  Primeiro registro     : {periodo[0]}")
        print(CIANO + f"  Ultimo registro       : {periodo[1]}")

    print()
    print(AZUL + "▸ TOP 10 ATIVOS POR QUANTIDADE DE CANDLES")
    for linha in top:
        print(
            CIANO + f"{linha[0]:<18} | {linha[1]:>7,} candles"
            + BRANCO + f" | Min {linha[2]} | Max {linha[3]}"
        )
        print(BRANCO + f"                   {linha[4]} -> {linha[5]}")

    return total, ativos


# ============================================================
# EXECUCAO PRINCIPAL
# ============================================================

def main():
    args = parse_args()
    try:
        args.symbols = validar_simbolos(args.symbols)
    except ValueError as exc:
        print(VERMELHO + f"✗ Lista de ativos invalida: {exc}")
        return 2
    if mt5 is None:
        print(VERMELHO + "MetaTrader5 package is required for live M1 extraction.")
        return 2

    try:
        data_alvo, inicio_utc, fim_utc = obter_intervalo_utc(args.data_alvo)
    except ValueError:
        print(VERMELHO + "✗ Data invalida. Utilize o formato YYYY-MM-DD.")
        return 2

    db_path = Path(args.db_path).expanduser().resolve()

    print()
    print(AZUL + "╔" + "═" * 78 + "╗")
    print(AZUL + "║" + " GEO_TRADE | EXTRACAO HISTORICA M1 ".center(78) + "║")
    print(AZUL + "╚" + "═" * 78 + "╝")
    print(CIANO + "  Desenvolvido por Nadison Roberto | NR TECH | © 2026")
    print()
    print(AZUL + "▸ CONFIGURACAO")
    print(CIANO + f"  Data local          : {data_alvo:%d/%m/%Y}")
    print(CIANO + f"  Inicio UTC          : {inicio_utc.isoformat()}")
    print(CIANO + f"  Fim UTC (exclusivo) : {fim_utc.isoformat()}")
    print(CIANO + f"  Timeframe           : {TIMEFRAME_NOME}")
    print(CIANO + f"  Banco               : {db_path}")
    print()

    conn = None
    mt5_inicializado = False
    inicio_execucao = time.time()

    processados = 0
    com_dados = 0
    sem_dados = 0
    erros = 0
    novos_candles = 0

    try:
        print(AZUL + "▸ INICIALIZANDO META TRADER 5...")
        if not mt5.initialize(path=args.terminal_path, timeout=120000):
            print(VERMELHO + f"✗ Falha no MT5: {mt5.last_error()}")
            return 1

        mt5_inicializado = True
        print(VERDE + "✓ MetaTrader 5 conectado")

        versao = mt5.version()
        conta = mt5.account_info()
        if conta is None:
            raise RuntimeError(f"MT5 account is not authenticated: {mt5.last_error()}")
        print(CIANO + f"  Versao MT5 : {versao}")
        print(CIANO + f"  Servidor   : {conta.server}")
        print(CIANO + f"  Moeda      : {conta.currency}")
        print(CIANO + f"  Saldo      : {conta.balance}")

        conn = preparar_banco(db_path)
        cursor = conn.cursor()
        print(VERDE + f"✓ SQLite preparado: {db_path}")

        if args.symbols:
            ativos = []
            for nome in args.symbols:
                info = mt5.symbol_info(nome)
                if info is None:
                    erros += 1
                    print(AMARELO + f"⚠ Ativo nao encontrado no MT5: {nome}")
                else:
                    ativos.append(info)
        else:
            ativos = mt5.symbols_get()
            if ativos is None:
                raise RuntimeError(
                    f"Falha ao consultar ativos do MT5: {mt5.last_error()}"
                )

        total_ativos = len(ativos)
        print(CIANO + f"✓ {total_ativos} ativos identificados")
        print()
        print(AZUL + "═" * 80)
        print(AZUL + " INICIO DA EXTRACAO ")
        print(AZUL + "═" * 80)

        for indice, info in enumerate(ativos, start=1):
            symbol = info.name
            processados += 1

            print(
                AZUL + f"[{indice:04d}/{total_ativos:04d}] "
                + CIANO + f"{symbol:<18}"
                + BRANCO + f" | {TIMEFRAME_NOME} | {data_alvo:%d/%m/%Y}"
            )

            try:
                if not mt5.symbol_select(symbol, True):
                    erros += 1
                    print(AMARELO + f"   ⚠ Nao foi possivel selecionar: {mt5.last_error()}")
                    continue

                gravar_metadados_ativo(cursor, info)

                rates = mt5.copy_rates_range(
                    symbol, TIMEFRAME, inicio_utc, fim_utc
                )

                if rates is None:
                    erros += 1
                    print(AMARELO + f"   ⚠ MT5 nao retornou historico: {mt5.last_error()}")
                    conn.rollback()
                    continue

                if len(rates) == 0:
                    sem_dados += 1
                    print(AMARELO + "   ⚠ Nenhum candle disponivel para o periodo.")
                    conn.commit()
                    continue

                resultado = gravar_candles(
                    cursor, symbol, rates, inicio_utc, fim_utc
                )
                conn.commit()

                if resultado["encontrados"] == 0:
                    sem_dados += 1
                    print(AMARELO + "   ⚠ Nenhum candle dentro do intervalo solicitado.")
                    continue

                com_dados += 1
                novos_candles += resultado["inseridos"]

                primeiro = resultado["primeiro"].strftime("%H:%M:%S UTC")
                ultimo = resultado["ultimo"].strftime("%H:%M:%S UTC")

                print(CIANO + f"   ✓ Candles encontrados : {resultado['encontrados']:>6}")
                print(CIANO + f"   ✓ Novos no banco      : {resultado['inseridos']:>6}")
                if resultado["rejeitados"]:
                    print(AMARELO + f"   ⚠ Candles rejeitados  : {resultado['rejeitados']:>6}")
                if resultado["conflitos_banco"]:
                    print(AMARELO + f"   ⚠ Conflitos com banco : {resultado['conflitos_banco']:>6}")
                print(BRANCO + f"   │ Horario UTC         : {primeiro} -> {ultimo}")
                print(BRANCO + f"   │ Maxima              : {resultado['maxima']}")
                print(BRANCO + f"   │ Minima              : {resultado['minima']}")
                print(CIANO + "   └────────────────────────────────────────────────────")

            except Exception as erro_ativo:
                conn.rollback()
                erros += 1
                print(VERMELHO + f"   ✗ ERRO NO ATIVO {symbol}: {erro_ativo}")

            time.sleep(PAUSA_ATIVO)

        conn.commit()
        total_banco, ativos_banco = mostrar_validacao(conn, data_alvo)

        duracao = time.time() - inicio_execucao
        print()
        print(AZUL + "═" * 80)
        print(AZUL + " RESUMO DA EXECUCAO ")
        print(AZUL + "═" * 80)
        print(CIANO + f"  Ativos processados : {processados}")
        print(CIANO + f"  Ativos com dados   : {com_dados}")
        print(AMARELO + f"  Ativos sem dados   : {sem_dados}")
        print(VERMELHO + f"  Ativos com erro    : {erros}")
        print(CIANO + f"  Novos candles      : {novos_candles:,}")
        print(CIANO + f"  Candles no banco   : {total_banco:,}")
        print(CIANO + f"  Ativos no banco    : {ativos_banco}")
        print(CIANO + f"  Tempo total        : {duracao:.1f} segundos")
        print(CIANO + f"  Arquivo SQLite     : {db_path}")

        if erros:
            print(AMARELO + "⚠ Execucao concluida com erros em um ou mais ativos.")
        else:
            print(VERDE + "✓ Extracao finalizada sem erros por ativo.")

    except KeyboardInterrupt:
        print(AMARELO + "\n⚠ Execucao interrompida pelo usuario. Dados ja confirmados foram preservados.")
        if conn:
            # Each completed symbol is committed independently. Roll back only
            # the current in-flight symbol instead of publishing a partial batch.
            conn.rollback()
        return 130

    except Exception as erro:
        print(VERMELHO + f"\n✗ ERRO FATAL: {erro}")
        return 1

    finally:
        if conn is not None:
            conn.close()
            print(CIANO + "✓ Conexao SQLite encerrada")

        if mt5_inicializado:
            mt5.shutdown()
            print(CIANO + "✓ MetaTrader 5 encerrado")

    if not args.no_open_db and db_path.exists():
        abrir_db_browser(db_path)

    print()
    print(AZUL + "═" * 80)
    print(AZUL + " GEO_TRADE | PROCESSO FINALIZADO ")
    print(AZUL + "═" * 80)
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
