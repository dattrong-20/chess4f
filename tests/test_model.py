from datetime import datetime, timedelta, timezone

import pytest

from chess4f.model import train, predict
from chess4f.storage import Lake


def test_model_temporal_split_and_scope(lake_root):
    # Synthetic data is only a test fixture, never dashboard/demo evidence.
    rows=[]
    for i in range(240):
        rows.append(dict(game_key=f"test:{i}",source="lichess",speed="blitz",
                         played_at=(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(days=i//12)).isoformat(),
                         white_elo=1400+i%400,black_elo=1500+i%300,
                         result=["1-0","0-1","1/2-1/2"][i%3]))
    Lake(lake_root).upsert("silver/games",rows,"game_key")
    report=train(lake_root,"lichess")
    assert report["trained_through"][:10] < report["test_start_day"]
    assert report["train_games"]+report["test_games"] == 240
    result=predict(lake_root,1500,1500,"lichess","blitz")
    assert sum(result["probabilities_from_white"].values()) == pytest.approx(1)
    with pytest.raises(ValueError):
        predict(lake_root,1500,1500,"chesscom","blitz")
