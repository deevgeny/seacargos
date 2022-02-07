# Seacargos - sea cargos aggregator web application.
# Copyright (C) 2022 Evgeny Deriglazov
# https://github.com/evgeny81d/seacargos/blob/main/LICENSE

import time
import requests
from seacargos.etl.oneline import container_request_payload, extract_schedule_data
from seacargos.etl.oneline import extract_container_data
from seacargos.etl.oneline import schedule_request_payload
from seacargos.etl.oneline import extract_data

URL = "https://ecomm.one-line.com/ecom/CUP_HOM_3301GS.do"

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

def test_extract_container_data():
    """Test extract_container_data() function."""
    # Prepare payload with booking number
    payload = {
            '_search': 'false', 'nd': str(time.time_ns())[:-6],
            'rows': '10000', 'page': '1', 'sidx': '',
            'sord': 'asc', 'f_cmd': '121', 'search_type': 'A',
            'search_name': "OSAB76633400", 'cust_cd': '',
        }
    
    # Check condition with booking number
    r = requests.get(URL, params=payload)
    check = r.json().get("list", None)
    if check and isinstance(check, list):
        check[0].pop("hashColumns", None)
    data = extract_container_data(payload)
    assert data == check[0]

    # Check condition with container number
    payload["search_name"] = "KKTU6079875"
    r = requests.get(URL, params=payload)
    check = r.json().get("list", None)
    if check and isinstance(check, list):
        check[0].pop("hashColumns", None)
    data = extract_container_data(payload)
    assert data == check[0]

    # Check condition for wrong number
    payload["search_name"] = "--test--"
    data = extract_container_data(payload)
    assert data == False
    with open("etl.log", "r") as f:
        check = f.read().split("\n")
    assert "No details data for --test--" in check[-1]

def test_schedule_request_payload():
    """Test schedule_request_payload() function."""
    # Prepare test data
    check = {
            '_search': 'false', 'f_cmd': '125', 'cntr_no': "KKTU6079875",
            'bkg_no': '', 'cop_no': None
        }
    cntr_data = {"cntrNo": "KKTU6079875", "copNo": None}
    # Run test
    payload = schedule_request_payload(cntr_data)
    assert payload == check

def test_extract_schedule_data():
    """Test extract_schedule_data() function."""
    # Prepare payload
    # Run this if explicit declaration fails
    #query = {"cntrNo": "KKTU6079875"}
    #cntr_payload = container_request_payload(query)
    #cntr_data = extract_container_data(cntr_payload)
    #schedule_payload = schedule_request_payload(cntr_data)
    #assert schedule_payload == 1
    schedule_payload = {
        "_search": "false", "bkg_no": "", "cntr_no": "KKTU6079875",
        "cop_no": "COSA1C20995300", "f_cmd": "125"
        }
    
    # Check condition for container and cop number
    data = extract_schedule_data(schedule_payload)
    r = requests.get(URL, params=schedule_payload)
    check_data = r.json()
    if "list" in check_data:
        check = check_data["list"]
        check[0].pop("hashColumns", None)
    assert data == check

    # Check condition for wrong number (log record)
    schedule_payload["cntr_no"] = "--test--"
    schedule_payload["cop_no"] = None
    data = extract_schedule_data(schedule_payload)
    assert data == False
    with open("etl.log", "r") as f:
        check = f.read().split("\n")
    assert "No schedule data for container --test--" in check[-1]

def test_extract_data():
    """Test extract_data() function."""
    # Use bkgNo to extract data and check
    data = extract_data({"bkgNo": "OSAB76633400"})
    assert data["query"] == {"bkgNo": "OSAB76633400"}
    assert "container_data" in data
    assert "schedule_data" in data

    # Empty query condition
    data = extract_data({"empty": ""})
    assert data == False
    with open("etl.log", "r") as f:
        check = f.read().split("\n")
    assert "No container data for {'empty': ''}" in check[-1]

    # If schedule data - not covered inside extract_data()

