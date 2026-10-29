"""Experimental PRE-GAME W/D/L baseline. No final opening label or future moves.

This is intentionally not an engine or a calibrated per-position win predictor.
Artifacts are local trusted files; never load user-uploaded pickle/joblib models.
"""
import uuid
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .storage import Lake, atomic_json, utc_now


def features(white, black):
    return [white-black, (white+black)/2]


def train(root, source, speed="blitz"):
    lake = Lake(root)
    with lake.connection() as con:
        rows = con.execute("""SELECT game_key, played_at, white_elo, black_elo, result
            FROM silver_games WHERE source=? AND speed=? AND white_elo IS NOT NULL
            AND black_elo IS NOT NULL ORDER BY played_at, game_key""", [source,speed]).fetchall()
    if len(rows) < 200:
        raise ValueError("Need at least 200 completed games in one platform/time-control scope")
    split_day = rows[int(len(rows)*.7)][1][:10]
    train_rows = [r for r in rows if r[1][:10] < split_day]
    test_rows = [r for r in rows if r[1][:10] >= split_day]
    if len(train_rows) < 100 or len(test_rows) < 40:
        raise ValueError("Need multiple dates and adequate temporal train/test sizes; refusing random split")
    labels = {"0-1":"loss", "1/2-1/2":"draw", "1-0":"win"}
    def arrays(rs):
        return np.array([features(r[2],r[3]) for r in rs]), np.array([labels[r[4]] for r in rs])
    x,y = arrays(train_rows); xt,yt = arrays(test_rows)
    if set(y) != {"win","draw","loss"}:
        raise ValueError("Training data must contain all three outcomes")
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=42))
    model.fit(x,y)
    probabilities = model.predict_proba(xt)
    classes = list(model.classes_)
    truth = np.array([[int(v==c) for c in classes] for v in yt])
    prior = np.array([(y==c).mean() for c in classes])
    baseline = np.tile(prior,(len(yt),1))
    model_id = uuid.uuid4().hex
    report = dict(model_id=model_id, kind="experimental_pregame_logistic_regression",
                  trained_at=utc_now(), source=source, speed=speed,
                  train_games=len(y), test_games=len(yt), test_start_day=split_day,
                  trained_through=max(r[1] for r in train_rows), classes=classes,
                  features=["elo_difference","average_elo"],
                  log_loss=float(log_loss(yt,probabilities,labels=classes)),
                  baseline_log_loss=float(log_loss(yt,baseline,labels=classes)),
                  multiclass_brier=float(np.mean(np.sum((probabilities-truth)**2,axis=1))),
                  baseline_multiclass_brier=float(np.mean(np.sum((baseline-truth)**2,axis=1))),
                  rating_min=int(min(min(r[2],r[3]) for r in train_rows)),
                  rating_max=int(max(max(r[2],r[3]) for r in train_rows)),
                  delta_versions=lake.versions(),
                  limitations="Small/selected data; no independent calibration set; not validated for live assistance or arbitrary players")
    report["beats_prior_log_loss"] = report["log_loss"] < report["baseline_log_loss"]
    folder = Path(root) / "models" / model_id
    folder.mkdir(parents=True)
    joblib.dump(model,folder / "model.joblib")
    atomic_json(folder / "report.json",report)
    atomic_json(Path(root)/"models/latest.json",report)
    return report


def predict(root, white_elo, black_elo, source, speed):
    import json
    latest = Path(root)/"models/latest.json"
    if not latest.exists():
        raise ValueError("No trained model")
    report = json.loads(latest.read_text(encoding="utf-8"))
    if source != report["source"] or speed != report["speed"]:
        raise ValueError("Platform/time control differs from training scope")
    if not all(report["rating_min"] <= n <= report["rating_max"] for n in [white_elo,black_elo]):
        raise ValueError("Rating outside observed training range")
    model = joblib.load(Path(root)/"models"/report["model_id"]/"model.joblib")
    probs = dict(zip(model.classes_,map(float,model.predict_proba([features(white_elo,black_elo)])[0])))
    return dict(probabilities_from_white=probs, white_expected_score=probs["win"]+.5*probs["draw"],
                model_id=report["model_id"], kind=report["kind"], limitations=report["limitations"])
