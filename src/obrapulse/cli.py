"""CLI: obrapulse {generate-data|train|run|serve|demo}."""

from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from .classifier.ml import MLClassifier
from .config import Settings, setup_logging
from .generator import write_sample_data
from .pipeline import run_pipeline


def cmd_generate(s: Settings, args) -> None:
    counts = write_sample_data(str(s.data_dir), days=args.days)
    print(json.dumps(counts, indent=2))


def cmd_train(s: Settings, args) -> None:
    path = args.data or s.data_dir / "historico_etiquetado.csv"
    df = pd.read_csv(path)
    model, metrics = MLClassifier.train(df)
    model.save(s.model_path, metrics)
    print(f"Modelo guardado en {s.model_path}")
    print(f"accuracy={metrics['accuracy']}  macro_f1={metrics['macro_f1']}")


def cmd_run(s: Settings, args) -> None:
    result = run_pipeline(s, args.partes)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_serve(s: Settings, args) -> None:
    import uvicorn

    uvicorn.run("obrapulse.api:app_factory", factory=True, host=args.host, port=args.port)


def cmd_demo(s: Settings, args) -> None:
    cmd_generate(s, argparse.Namespace(days=84))
    cmd_train(s, argparse.Namespace(data=None))
    cmd_run(s, argparse.Namespace(partes=None))
    print(f"\nAbrí el reporte: {s.reports_dir / 'reporte_latest.html'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="obrapulse", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("generate-data", help="genera partes diarios sintéticos de ejemplo")
    p.add_argument("--days", type=int, default=84)
    p.set_defaults(fn=cmd_generate)

    p = sub.add_parser("train", help="entrena el clasificador ML con el histórico etiquetado")
    p.add_argument("--data", default=None)
    p.set_defaults(fn=cmd_train)

    p = sub.add_parser("run", help="ejecuta el pipeline completo y genera el reporte")
    p.add_argument("--partes", default=None, help="CSV de partes diarios")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("serve", help="levanta la API REST")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("demo", help="generate-data + train + run en un paso")
    p.set_defaults(fn=cmd_demo)

    args = parser.parse_args(argv)
    settings = Settings.from_env()
    setup_logging(settings.log_level)
    try:
        args.fn(settings, args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
