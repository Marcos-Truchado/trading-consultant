"""
analysis_history.py - Persistencia del historial de análisis.

SQLite vía peewee (ya en requirements.txt). Guarda un snapshot por análisis
exitoso para poder comparar evolución del score y recargar un análisis previo
desde el dashboard. Sin dependencias nuevas.
"""
import os

from peewee import SqliteDatabase, Model, CharField, FloatField, DateTimeField, DatabaseProxy
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analisis_history.db")

_db = DatabaseProxy()
_db.initialize(SqliteDatabase(DB_PATH))


class AnalysisRecord(Model):
    ticker = CharField()
    timestamp = DateTimeField(default=datetime.datetime.now)
    score = FloatField()
    veredicto = CharField()
    action = CharField()
    precio = FloatField()
    rr = FloatField(null=True)
    direccion = CharField()
    estado_onda = CharField()
    deviation = FloatField()
    period = CharField()
    bar_size = CharField()

    class Meta:
        database = _db


def ensure_table() -> None:
    _db.connect(reuse_if_open=True)
    _db.create_tables([AnalysisRecord])


def record_analysis(*, ticker: str, score: float, veredicto: str, action: str,
                    precio: float, rr: float, direccion: str, estado_onda: str,
                    deviation: float, period: str, bar_size: str) -> int:
    ensure_table()
    rec = AnalysisRecord.create(
        ticker=ticker, score=float(score), veredicto=veredicto, action=action,
        precio=float(precio), rr=rr, direccion=direccion, estado_onda=estado_onda,
        deviation=float(deviation), period=period, bar_size=bar_size,
    )
    return rec.id


def _to_dict(rec: AnalysisRecord) -> dict:
    return {
        "id": rec.id,
        "ticker": rec.ticker,
        "timestamp": rec.timestamp.isoformat(sep=" "),
        "score": rec.score,
        "veredicto": rec.veredicto,
        "action": rec.action,
        "precio": rec.precio,
        "rr": rec.rr,
        "direccion": rec.direccion,
        "estado_onda": rec.estado_onda,
        "deviation": rec.deviation,
        "period": rec.period,
        "bar_size": rec.bar_size,
    }


def recent_analyses(limit: int = 50) -> list:
    ensure_table()
    rows = (AnalysisRecord.select()
            .order_by(AnalysisRecord.timestamp.desc())
            .limit(limit))
    return [_to_dict(r) for r in rows]


def load_analysis(record_id: int):
    """Devuelve el registro como dict, o None si no existe."""
    ensure_table()
    try:
        rec = AnalysisRecord.get_by_id(record_id)
    except AnalysisRecord.DoesNotExist:
        return None
    return _to_dict(rec)
