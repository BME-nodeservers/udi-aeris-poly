#!/usr/bin/env python3
"""
Polyglot v2 node server AERIS weather data
Copyright (C) 2019 Robert Paauwe
"""

CLOUD = False
try:
    import polyinterface
except ImportError:
    import pgc_interface as polyinterface
    CLOUD = True
import sys
import time
import datetime
import urllib3
import socket
import math
import re
import json
import aeris_daily

LOGGER = polyinterface.LOGGER

class Controller(polyinterface.Controller):
    id = 'weather'
    #id = 'controller'
    hint = [0,0,0,0]
    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        self.name = 'AERIS Weather'
        self.address = 'weather'
        self.primary = self.address
        self.location = ''
        self.apikey = ''
        self.units = 'metric'
        self.configured = False
        self.myConfig = {}
        self.latitude = 0
        self.longitude = 0
        self.fcast = {}
        self.plant_type = 0.23
        self.elevation = 0
        self.uom = {}

        self.poly.onConfig(self.process_config)

    # Process changes to customParameters
    def process_config(self, config):
        if 'customParams' in config:
            # Check if anything we care about was changed...
            if config['customParams'] != self.myConfig:
                changed = False
                if 'Location' in config['customParams']:
                    if self.location != config['customParams']['Location']:
                        self.location = config['customParams']['Location']
                        changed = True
                if 'APIkey' in config['customParams']:
                    if self.apikey != config['customParams']['APIkey']:
                        self.apikey = config['customParams']['APIkey']
                        changed = True
                if 'Elevation' in config['customParams']:
                    if self.elevation != config['customParams']['Elevation']:
                        self.elevation = config['customParams']['Elevation']
                        changed = False
                if 'Plant Type' in config['customParams']:
                    if self.plant_type != config['customParams']['Plant Type']:
                        self.plant_type = config['customParams']['Plant Type']
                        changed = False
                if 'Units' in config['customParams']:
                    if self.units != config['customParams']['Units']:
                        self.units = config['customParams']['Units']
                        changed = True
                        try:
                            self.set_driver_uom(self.units)
                        except:
                            LOGGER.debug('set driver units failed.')

                self.myConfig = config['customParams']
                if changed:
                    self.removeNoticesAll()
                    self.configured = True

                    if self.location == '':
                        self.addNotice("Location parameter must be set");
                        self.configured = False
                    if self.apikey == '':
                        self.addNotice("OpenWeatherMap API ID must be set");
                        self.configured = False

    def start(self):
        LOGGER.info('Starting node server')
        for day in range(1,6):
            address = 'forecast_' + str(day)
            title = 'Forecast ' + str(day)
            try:
                node = owm_daily.DailyNode(self, self.address, address, title)
                self.addNode(node)
            except:
                LOGGER.error('Failed to create forecast node ' + title)

        self.check_params()
        # TODO: Discovery
        LOGGER.info('Node server started')

        # Do an initial query to get filled in as soon as possible
        self.query_conditions()
        #self.query_forecast()

    def longPoll(self):
        LOGGER.info('longpoll')
        #self.query_forecast()

    def shortPoll(self):
        self.query_conditions()

    # Wrap all the setDriver calls so that we can check that the 
    # value exist first.
    def update_driver(self, driver, value, uom):
        try:
            self.setDriver(driver, float(value), report=True, force=False, uom=uom)
            #LOGGER.info('setDriver (%s, %f)' %(driver, float(value)))
        except:
            LOGGER.debug('Missing data for driver ' + driver)

    def query_conditions(self):
        # Query for the current conditions. We can do this fairly
        # frequently, probably as often as once a minute.
        #
        # By default JSON is returned
        # http://api.openweathermap.org/data/2.5/weather?

        request = 'http://api.aerisapi.com/observations/'
        # if location looks like a zip code, treat it as such for backwards
        # compatibility
        if re.fullmatch(r'\d\d\d\d\d,..', self.location) != None:
            request += self.location
        elif re.fullmatch(r'\d\d\d\d\d', self.location) != None:
            request += self.location
        else:
            request += self.location

        request += '?client_id=JGlB9OD1KA1EvzoSkpBmJ'
        request += '&client_secret=xiZGRDGO61ZP2YZH1YDwVB6tuDMX4Zx3o9yeXDyI'
        #request += '&units=' + self.units

        LOGGER.debug('request = %s' % request)

        if not self.configured:
            LOGGER.info('Skipping connection because we aren\'t configured yet.')
            return

        http = urllib3.PoolManager()
        c = http.request('GET', request)
        wdata = c.data
        jdata = json.loads(wdata.decode('utf-8'))
        c.close()
        LOGGER.debug(jdata)

        '''
        try:
            self.latitude = jdata['coord']['lat']
            self.longitude = jdata['coord']['lon']

            # Query UV index data
            request = 'http://api.openweathermap.org/data/2.5/uvi?'
            request += 'appid=' + self.apikey
            # Only query by lat/lon so need to pull that from jdata
            request += '&lat=' + str(jdata['coord']['lat'])
            request += '&lon=' + str(jdata['coord']['lon'])
            try:
                c = http.request('GET', request)
                uv_data = json.loads(c.data.decode('utf-8'))
                c.close()
                LOGGER.debug('UV index = %f' % uv_data['value'])
            except:
                LOGGER.debug('UV data is not valid.')

            # for kicks, lets try getting pollution info
            request = 'http://api.openweathermap.org/pollution/v1/co/'
            request += str(jdata['coord']['lat']) + ','
            request += str(jdata['coord']['lon'])
            request += '/current.json?'
            request += 'appid=' + self.apikey
            # Only query by lat/lon so need to pull that from jdata
            LOGGER.debug(request)
            try:
                c = http.request('GET', request)
                pollution_data = json.loads(c.data.decode('utf-8'))
                c.close()
                LOGGER.debug(pollution_data)
            except:
                LOGGER.debug('pollution data is not valid')

        except:
            LOGGER.debug('Skipping UV and Pollution data, no location info')

        '''
        http.clear()
        # Should we check that jdata actually has something in it?
        if jdata == None:
            LOGGER.error('Current condition query returned no data')
            return

        '''
        Data from query has multiple units. Which one we want to use depends
        on what the user has selected.  Since we set the node to metric by
        default, lets just use those for testing.
        '''
        
        #jdata['response']['ob']['tempC']
        if 'response' not in jdata:
            LOGGER.error('No response object in query response.')
            return
        if 'ob' not in jdata['response']:
            LOGGER.error('No observation object in query response.')
            return

        ob = jdata['response']['ob']

        self.update_driver('CLITEMP', ob['tempC'], self.uom['CLITEMP'])
        self.update_driver('CLIHUM', ob['humidity'], self.uom['CLIHUM'])
        self.update_driver('BARPRES', ob['pressureMB'], self.uom['BARPRES'])
        self.update_driver('GV4', ob['windSpeedKPH'], self.uom['GV4'])
        self.update_driver('WINDDIR', ob['windDirDEG'], self.uom['WINDDIR'])
        self.update_driver('GV15', ob['visibilityKM'], self.uom['GV15'])
        self.update_driver('GV6', ob['precipMM'], self.uom['GV6'])

        '''
        TODO:
           - dewpoint
           - altimeter?
           - wind gusts
           - weather
           - heatindex
           - windchill
           - feelslike
           - snow depth
           - solar radiation
           - ceiling
           - light
           - QC / QCcode
           - sky
        '''


        '''
        #self.update_driver('GV0', jdata['main']['temp_max'], self.uom['GV0'])
        #self.update_driver('GV1', jdata['main']['temp_min'], self.uom['GV1'])
        if 'clouds' in jdata:
            self.update_driver('GV14', jdata['clouds']['all'], self.uom['GV14'])
        if 'weather' in jdata:
            self.update_driver('GV13', jdata['weather'][0]['id'], self.uom['GV13'])
        
        self.update_driver('GV16', uv_data['value'], self.uom['GV16'])
        '''

    def query_forecast(self):
        # Three hour forecast for 5 days (or about 30 entries). This
        # is probably too much data to send to the ISY and there isn't
        # really a good way to deal with this. Would it make sense
        # to pick one of the entries for the day and just use that?

        request = 'http://api.openweathermap.org/data/2.5/forecast?'
        # if location looks like a zip code, treat it as such for backwards
        # compatibility
        if re.fullmatch(r'\d\d\d\d\d,..', self.location) != None:
            request += 'zip=' + self.location
        elif re.fullmatch(r'\d\d\d\d\d', self.location) != None:
            request += 'zip=' + self.location
        else:
            request += self.location
        request += '&units=' + self.units
        request += '&appid=' + self.apikey

        LOGGER.debug('request = %s' % request)

        if not self.configured:
            LOGGER.info('Skipping connection because we aren\'t configured yet.')
            return

        http = urllib3.PoolManager()
        c = http.request('GET', request)
        wdata = c.data
        c.close()

        # query UV forecast
        request = 'http://api.openweathermap.org/data/2.5/uvi/forecast?'
        request += 'appid=' + self.apikey
        # Only query by lat/lon so need to pull that from jdata
        request += '&lat=' + str(self.latitude)
        request += '&lon=' + str(self.longitude)
        c = http.request('GET', request)
        uv_data = json.loads(c.data.decode('utf-8'))
        c.close()
        #LOGGER.debug(uv_data)

        http.clear()

        jdata = json.loads(wdata.decode('utf-8'))

        #LOGGER.debug(jdata)

        # Records are for 3 hour intervals starting at midnight UTC time
        # this makes it difficult to map to local day forecasts.
        # Also note that this may start in the middle of the current day
        # so we need to skip those values.  This also means that we may
        # not end at 21:00.
        day = 1
        start = False
        count = 0
        if 'list' in jdata:
            for forecast in jdata['list']:

                # we need to look at every 3 hr entry and build the 
                # temp and humidity min/max and also average for pressure
                # and wind speed. Looking at only the first 3 hrs isn't
                # really usefull
                dt = forecast['dt_txt'].split(' ')

                LOGGER.info('date and time: %s %s' % (dt[0], dt[1]))
                #if dt[1] != '12:00:00':
                #    continue

                if dt[1] == '00:00:00':
                    # Initialize values
                    self.fcast['temp_max'] = float(forecast['main']['temp_max'])
                    self.fcast['temp_min'] = float(forecast['main']['temp_min'])
                    self.fcast['Hmax'] = float(forecast['main']['humidity'])
                    self.fcast['Hmin'] = float(forecast['main']['humidity'])
                    self.fcast['pressure'] = float(forecast['main']['pressure'])
                    self.fcast['weather'] = float(forecast['weather'][0]['id'])
                    self.fcast['speed'] = float(forecast['wind']['speed'])
                    self.fcast['clouds'] = float(forecast['clouds']['all'])
                    self.fcast['dt'] = forecast['dt']
                    start = True
                    count = 1
                    try:
                        self.fcast['uv'] = uv_data[day - 1]['value']
                    except:
                        self.fcast['uv'] = 0
                elif start:
                    # check for high/low
                    if float(forecast['main']['temp_max']) > self.fcast['temp_max']:
                        self.fcast['temp_max'] = float(forecast['main']['temp_max'])
                    if float(forecast['main']['temp_min']) < self.fcast['temp_min']:
                        self.fcast['temp_min'] = float(forecast['main']['temp_min'])
                    if float(forecast['main']['humidity']) > self.fcast['Hmax']:
                        self.fcast['Hmax'] = float(forecast['main']['humidity'])
                    if float(forecast['main']['humidity']) < self.fcast['Hmin']:
                        self.fcast['Hmin'] = float(forecast['main']['humidity'])

                    # sum for averages
                    self.fcast['pressure'] += float(forecast['main']['pressure'])
                    self.fcast['speed'] += float(forecast['wind']['speed'])
                    self.fcast['clouds'] += float(forecast['clouds']['all'])
                    count += 1
                #else:


                if dt[1] == '21:00:00' and start:
                    self.fcast['pressure'] /= 8
                    self.fcast['speed'] /= 8
                    self.fcast['clouds'] /= 8
                    LOGGER.info(self.fcast)
                    # Update the forecast
                    address = 'forecast_' + str(day)
                    self.nodes[address].update_forecast(self.fcast, self.latitude, self.elevation, self.plant_type, self.units)
                    day += 1
                    start = False
                    count = 0

            if start:
                LOGGER.info('Partial day forecast ' + str(count))
                self.fcast['pressure'] /= count
                self.fcast['speed'] /= count
                self.fcast['clouds'] /= count
                LOGGER.info(self.fcast)
                 # Update the forecast
                address = 'forecast_' + str(day)
                self.nodes[address].update_forecast(self.fcast, self.latitude, 400, 0.23, self.units)


    def query(self):
        for node in self.nodes:
            self.nodes[node].reportDrivers()

    def discover(self, *args, **kwargs):
        # Create any additional nodes here
        LOGGER.info("In Discovery...")

    # Delete the node server from Polyglot
    def delete(self):
        LOGGER.info('Removing node server')

    def stop(self):
        LOGGER.info('Stopping node server')

    def update_profile(self, command):
        st = self.poly.installprofile()
        return st

    def check_params(self):

        if 'Location' in self.polyConfig['customParams']:
            self.location = self.polyConfig['customParams']['Location']
        if 'APIkey' in self.polyConfig['customParams']:
            self.apikey = self.polyConfig['customParams']['APIkey']
        if 'Elevation' in self.polyConfig['customParams']:
            self.elevation = self.polyConfig['customParams']['Elevation']
        if 'Plant Type' in self.polyConfig['customParams']:
            self.plant_type = self.polyConfig['customParams']['Plant Type']
        if 'Units' in self.polyConfig['customParams']:
            self.units = self.polyConfig['customParams']['Units']
        else:
            self.units = 'metric';

        self.configured = True

        self.addCustomParam( {
            'Location': self.location,
            'APIkey': self.apikey,
            'Units': self.units,
            'Elevation': self.elevation,
            'Plant Type': self.plant_type} )

        LOGGER.info('api id = %s' % self.apikey)

        self.removeNoticesAll()
        if self.location == '':
            self.addNotice("Location parameter must be set");
            self.configured = False
        if self.apikey == '':
            self.addNotice("OpenWeatherMap API ID must be set");
            self.configured = False

        self.set_driver_uom(self.units)

    # Set the uom dictionary based on current user units preference
    def set_driver_uom(self, units):
        LOGGER.info('New Configure driver units to ' + units)
        if units == 'metric':
            self.uom['ST'] = 2   # node server status
            self.uom['CLITEMP'] = 4   # temperature
            self.uom['CLIHUM'] = 22   # humidity
            self.uom['BARPRES'] = 118 # pressure
            self.uom['WINDDIR'] = 76  # direction
            self.uom['GV0'] = 4       # max temp
            self.uom['GV1'] = 4       # min temp
            self.uom['GV4'] = 49      # wind speed
            self.uom['GV6'] = 82      # rain
            self.uom['GV13'] = 25     # climate conditions
            self.uom['GV14'] = 22     # cloud conditions
            self.uom['GV15'] = 83     # visibility
            self.uom['GV16'] = 71     # UV index

            '''
            for day in range(1,6):
                address = 'forecast_' + str(day)
                self.nodes[address].set_driver_uom('metric')
            '''
        else:
            self.uom['ST'] = 2   # node server status
            self.uom['CLITEMP'] = 17  # temperature
            self.uom['CLIHUM'] = 22   # humidity
            self.uom['BARPRES'] = 118 # pressure
            self.uom['WINDDIR'] = 76  # direction
            self.uom['GV0'] = 17      # max temp
            self.uom['GV1'] = 17      # min temp
            self.uom['GV4'] = 48      # wind speed
            self.uom['GV6'] = 105     # rain
            self.uom['GV13'] = 25     # climate conditions
            self.uom['GV14'] = 22     # cloud conditions
            self.uom['GV15'] = 116    # visibility
            self.uom['GV16'] = 71     # UV index

            '''
            for day in range(1,6):
                address = 'forecast_' + str(day)
                self.nodes[address].set_driver_uom('imperial')
            '''

    def remove_notices_all(self, command):
        self.removeNoticesAll()


    commands = {
            'DISCOVER': discover,
            'UPDATE_PROFILE': update_profile,
            'REMOVE_NOTICES_ALL': remove_notices_all
            }

    # For this node server, all of the info is available in the single
    # controller node.
    #
    # TODO: Do we want to try and do evapotranspiration calculations? 
    #       maybe later as an enhancement.
    # TODO: Add forecast data
    drivers = [
            {'driver': 'ST', 'value': 1, 'uom': 2},   # node server status
            {'driver': 'CLITEMP', 'value': 0, 'uom': 4},   # temperature
            {'driver': 'CLIHUM', 'value': 0, 'uom': 22},   # humidity
            {'driver': 'BARPRES', 'value': 0, 'uom': 118}, # pressure
            {'driver': 'WINDDIR', 'value': 0, 'uom': 76},  # direction
            {'driver': 'GV0', 'value': 0, 'uom': 4},       # max temp
            {'driver': 'GV1', 'value': 0, 'uom': 4},       # min temp
            {'driver': 'GV4', 'value': 0, 'uom': 49},      # wind speed
            {'driver': 'GV6', 'value': 0, 'uom': 82},      # rain
            {'driver': 'GV13', 'value': 0, 'uom': 25},     # climate conditions
            {'driver': 'GV14', 'value': 0, 'uom': 22},     # cloud conditions
            {'driver': 'GV15', 'value': 0, 'uom': 83},     # visibility
            {'driver': 'GV16', 'value': 0, 'uom': 71},     # UV index
            ]


    
if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('OWM')
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        
