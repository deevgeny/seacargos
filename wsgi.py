# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

import os
from seacargos import create_app

os.environ["FLASK_ENV"] = "production"
app = create_app()
