"""API REST (FastAPI) para integrar el sistema con otras herramientas (Power BI, bots, ERP).

Seguridad: si `API_KEY` está definida, todos los endpoints (salvo /health) la exigen en el
header X-API-Key. Comparación en tiempo constante.
"""

from __future__ import annotations

import hmac
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import __version__, kpis, storage
from .anomalies import detect_ppc_drops
from .classifier.service import ClassificationService
from .config import Settings
from .taxonomy import CATEGORIES


class ClassifyRequest(BaseModel):
    descripcion: str = Field(
        min_length=3, max_length=1000, examples=["no llegó el hormigón, demora del proveedor"]
    )
    actividad: str = Field(default="", max_length=100)
    obra: str = Field(default="", max_length=50)


class ClassifyResponse(BaseModel):
    categoria: str
    categoria_nombre: str
    confianza: float
    metodo: str
    justificacion: str
    requiere_revision: bool


def create_app(
    settings: Settings | None = None, service: ClassificationService | None = None
) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="ObraPulse API",
        version=__version__,
        description="Clasificación de causas de no cumplimiento con IA y KPIs de obra (PPC, SPI).",
    )
    state: dict = {"service": service}

    def get_service() -> ClassificationService:
        if state["service"] is None:
            state["service"] = ClassificationService(settings)
        return state["service"]

    def auth(x_api_key: str | None = Header(default=None)) -> None:
        if settings.api_key and not hmac.compare_digest(x_api_key or "", settings.api_key):
            raise HTTPException(status_code=401, detail="API key inválida o ausente")

    def partes():
        if not storage.table_exists(settings.db_path, "partes"):
            raise HTTPException(
                status_code=409, detail="Aún no hay datos: ejecutar el pipeline (obrapulse run)"
            )
        df = storage.read_table(settings.db_path, "partes")
        df["cumplida"] = df["cumplida"].astype(bool)
        return df

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "modo": settings.classifier_mode,
            "llm_habilitado": settings.llm_enabled,
            "datos_cargados": storage.table_exists(settings.db_path, "partes"),
        }

    @app.post("/classify", response_model=ClassifyResponse, dependencies=[Depends(auth)])
    def classify(req: ClassifyRequest, svc: ClassificationService = Depends(get_service)):
        p = svc.classify_one(req.descripcion, req.actividad, req.obra)
        return ClassifyResponse(
            categoria=p.categoria,
            categoria_nombre=CATEGORIES[p.categoria],
            confianza=round(p.confianza, 4),
            metodo=p.metodo,
            justificacion=p.justificacion,
            requiere_revision=p.requiere_revision,
        )

    @app.get("/kpis", dependencies=[Depends(auth)])
    def get_kpis(obra: str | None = Query(default=None, max_length=20)) -> dict:
        df = partes()
        if obra:
            df = df[df["obra"] == obra]
            if df.empty:
                raise HTTPException(status_code=404, detail=f"Obra {obra!r} sin datos")
        return {k: round(float(v), 4) for k, v in kpis.totales(df).items()}

    @app.get("/obras", dependencies=[Depends(auth)])
    def get_obras() -> list[dict]:
        return kpis.resumen_obras(partes()).round(4).to_dict("records")

    @app.get("/datos", dependencies=[Depends(auth)])
    def get_datos(
        obra: str | None = Query(default=None, max_length=50),
        fecha_desde: date | None = Query(default=None),
        fecha_hasta: date | None = Query(default=None),
        limite: int = Query(default=10000, ge=1, le=50000),
        desplazamiento: int = Query(default=0, ge=0),
    ) -> list[dict]:
        """Detalle de partes enriquecidos, preparado para BI y análisis externo.

        El límite y desplazamiento permiten consultar grandes conjuntos por páginas.
        Las columnas derivadas incluyen PPC/cumplimiento, valores planificados/ejecutados,
        pérdidas estimadas y categoría de causa cuando el registro es un desvío.
        """
        df = partes()
        if obra:
            df = df[df["obra"] == obra]
        if fecha_desde:
            df = df[df["fecha"] >= fecha_desde.isoformat()]
        if fecha_hasta:
            df = df[df["fecha"] <= fecha_hasta.isoformat()]
        df = df.sort_values(["fecha", "obra", "registro_id"])
        page = df.iloc[desplazamiento : desplazamiento + limite].copy()
        # Evita NaN/NaT en la respuesta JSON, que algunas herramientas BI no interpretan.
        page = page.astype(object).where(page.notna(), None)
        return page.to_dict("records")

    @app.get("/curva-s", dependencies=[Depends(auth)])
    def get_curva_s(
        obra: str | None = Query(default=None, max_length=50),
        fecha_desde: date | None = Query(default=None),
        fecha_hasta: date | None = Query(default=None),
    ) -> list[dict]:
        """Serie temporal de valor planificado/ejecutado y acumulados por obra."""
        df = partes()
        if obra:
            df = df[df["obra"] == obra]
        if fecha_desde:
            df = df[df["fecha"] >= fecha_desde.isoformat()]
        if fecha_hasta:
            df = df[df["fecha"] <= fecha_hasta.isoformat()]
        if df.empty:
            return []
        return kpis.curva_s(df).to_dict("records")

    @app.get("/calidad-datos", dependencies=[Depends(auth)])
    def get_calidad_datos() -> dict:
        """Resumen de calidad de la última corrida, incluidos registros en cuarentena."""
        db = settings.db_path
        validos = len(partes())
        rechazados = (
            len(storage.read_table(db, "cuarentena_partes"))
            if storage.table_exists(db, "cuarentena_partes")
            else 0
        )
        desvios = storage.read_table(db, "desvios") if storage.table_exists(db, "desvios") else None
        a_revision = (
            int(desvios["requiere_revision"].fillna(False).astype(bool).sum())
            if desvios is not None and "requiere_revision" in desvios
            else 0
        )
        corridas = (
            storage.read_table(db, "corridas") if storage.table_exists(db, "corridas") else None
        )
        ultima_corrida = (
            corridas.iloc[-1].to_dict() if corridas is not None and not corridas.empty else {}
        )
        return {
            "partes_validos": validos,
            "partes_rechazados": rechazados,
            "total_recibidos": validos + rechazados,
            "registros_a_revision": a_revision,
            "ultima_corrida": ultima_corrida,
        }

    @app.get("/pareto", dependencies=[Depends(auth)])
    def get_pareto(
        por: str = Query(default="categoria", pattern="^(categoria|obra|actividad)$"),
    ) -> list[dict]:
        partes()
        d = storage.read_table(settings.db_path, "desvios")
        return kpis.pareto(d, by=por).to_dict("records")

    @app.get("/anomalies", dependencies=[Depends(auth)])
    def get_anomalies() -> list[dict]:
        df = partes()
        d = storage.read_table(settings.db_path, "desvios")
        return detect_ppc_drops(df, d).to_dict("records")

    @app.get("/report", dependencies=[Depends(auth)])
    def get_report():
        path = Path(settings.reports_dir) / "reporte_latest.html"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Reporte no generado todavía")
        return FileResponse(path, media_type="text/html")

    return app


def app_factory() -> FastAPI:  # para `uvicorn obrapulse.api:app_factory --factory`
    return create_app()
