# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

import time
from seacargos.etl.oneline import container_request_payload

def test_container_request_payload():
    """Test container_request_payload() function."""
    # Prepare test data
    check = {
            '_search': 'false', 'nd': str(time.time_ns())[:-6],
            'rows': '10000', 'page': '1', 'sidx': '',
            'sord': 'asc', 'f_cmd': '121', 'search_type': 'A',
            'search_name': None, 'cust_cd': '',
        }

    # Booking number condition
    check["search_name"] = "booking"
    result = container_request_payload({"bkgNo": "booking"})
    assert result == check
    
    # Container number condition
    check["search_name"] = "container"
    result = container_request_payload({"cntrNo": "container"})
    assert result == check
    
    # Empty condition
    check["search_name"] = None
    result = container_request_payload({"empty": ""})
    assert result == check