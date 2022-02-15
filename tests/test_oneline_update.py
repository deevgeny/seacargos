# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

from seacargos.etl.oneline_update import log

def test_log():
    """Test log() function."""
    log("test log")
    with open("etl.log", "r") as f:
        log_data =f.read().split("\n")
    check = log_data[-1].split(" ")
    assert len(check) == 4