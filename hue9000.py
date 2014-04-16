#!/usr/bin/python

import phue
import time
import threading
import pprint
import RPi.GPIO as io
import logging
import collections
import datetime
#import traceback
import urllib2
import json
import os
import ConfigParser
import TSL2561

PIR_PIN = 18
 
pp = pprint.PrettyPrinter()
logging.basicConfig(format='%(asctime)s: %(levelname)s %(message)s', level=logging.INFO)

LightSetting = collections.namedtuple('LightSetting', ['command','timeout'])

bridge_ip = None
light_group = None
wu_api_key = None
zip_code = None

LOOP_DELAY = 1
DAY_TIMEOUT = 1800
NIGHT_TIMEOUT = 180

DAYTIME_DARKNESS_THRESHOLD = 10.0

MORNING_COMMAND  = {'ct' : 447, 'bri' : 240, 'on' : True}
DAY_COMMAND = {'ct' : 328, 'bri' : 254, 'on' : True}
EVENING_COMMAND = {'ct' : 328, 'bri' : 254, 'on' : True}
NIGHT_COMMAND  = {'ct' : 328, 'bri' : 127, 'on' : True}

weather = None
tsl = None

def refresh_weather():
	global weather
	f = urllib2.urlopen('http://api.wunderground.com/api/' + wu_api_key + 
	                    '/astronomy/conditions/q/' + wu_station + '.json')
	json_string = f.read()
	weather = json.loads(json_string)
	f.close()
#	logging.info('Sunrise hour ' + weather['sun_phase']['sunrise']['hour'] + ' min ' + weather['sun_phase']['sunrise']['minute'])

def get_light_setting():
	now = datetime.datetime.now()

	check_time = now.replace(hour=6, minute=0, second=0)
	if (now < check_time):
		return LightSetting(command = NIGHT_COMMAND, timeout = NIGHT_TIMEOUT)

#	check_time = now.replace(hour=7, minute=0, second=0)
	check_time = now.replace(hour=int(weather['sun_phase']['sunrise']['hour']), 
							 minute=int(weather['sun_phase']['sunrise']['minute']), 
							 second=0)
	check_time += datetime.timedelta(hours=1)
	if now < check_time:
		return LightSetting(command = MORNING_COMMAND, timeout = DAY_TIMEOUT)
			
	check_time = now.replace(hour=int(weather['sun_phase']['sunset']['hour']), 
						     minute=int(weather['sun_phase']['sunset']['minute']), 
						     second=0)
	if now < check_time:
	    lux = tsl.readlux()
	    logging.info('Lux = ' + lux)
		if (lux < DAYTIME_DARKNESS_THRESHOLD):
			return LightSetting(command = DAY_COMMAND, timeout = DAY_TIMEOUT)
		else:
			return None
		
	check_time = now.replace(hour=22, minute=30, second=0)
	if now < check_time:
		return LightSetting(command = EVENING_COMMAND, timeout = DAY_TIMEOUT)
	else:
		return LightSetting(command = NIGHT_COMMAND, timeout = NIGHT_TIMEOUT)
	
    
def all_on(command):
	logging.info('Lights on')
#	bridge.set_group(light_group, command)
	bridge.set_group(light_group, command)

def all_off():
	logging.info('Lights off')
	bridge.set_group(light_group, 'on', False)
	
def motion_detected():
	return io.input(PIR_PIN)

# Read config file
if os.access(os.getenv('HOME'), os.W_OK):
	config_file_path = os.path.join(
		os.getenv('HOME'), '.hue9000config')
else:
	config_file_path = os.path.join(os.getcwd(), '.hue9000config')
	
logging.info(config_file_path)

try:
	config = ConfigParser.SafeConfigParser()
	config.read(config_file_path)
	bridge_ip = config.get('hue', 'bridge_ip')
	light_group = config.get('hue', 'light_group')
	wu_api_key = config.get('weather', 'wu_api_key')
	wu_station = config.get('weather', 'wu_station')
except Exception as e:
	logging.error('Error opening/reading config file: ' + config_file_path)
	print e
	exit(1)

logging.info(light_group)

# Set up the pin we'll be reading the PIR on
io.setmode(io.BCM)
io.setup(PIR_PIN, io.IN)         
	
# Connect to the hue bridge
try:
	bridge = phue.Bridge(bridge_ip)
except Exception as e:
	print "Unable to connect to hue bridge."
	print e
	exit(1)

light_timer = None
light_setting = None

refresh_weather()

# Set up light sensor
tsl = TSL2561

while True:
	if motion_detected():
#		logging.info('Motion Detected')
		light_setting = get_light_setting()
		if light_setting:
			# Only run through this logic if the time of day or conditions require
			# the light to be on
			if light_timer is None:
				# No timer created yet, first time through, turn on lights.
				all_on(light_setting.command)
			else:
				if light_timer.isAlive():
					# We had a running timer, which means the lights were on. We'll just kill
					# this timer and create a new one.
					light_timer.cancel()
				else:
					# No timer running, lights must be off, turn on.
					all_on(light_setting.command)
			light_timer = threading.Timer(light_setting.timeout, all_off)
			light_timer.start()
		
#	pp.pprint(bridge.get_group(LIGHT_GROUP))
	time.sleep(LOOP_DELAY)