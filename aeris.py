#!/usr/bin/env python3
"""
Polyglot v3 node server AERIS weather data
Copyright (C) 2019,2020,2021 Robert Paauwe
"""

import udi_interface
import sys
import time
from nodes import aeris
from nodes import aeris_daily

LOGGER = udi_interface.LOGGER

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([aeris.Controller, aeris_daily.DailyNode])
        polyglot.start('2.0.10')
        control = aeris.Controller(polyglot, 'controller', 'controller', 'AERIS Weather')
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        

