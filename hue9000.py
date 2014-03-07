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

PIR_PIN = 18
 
pp = pprint.PrettyPrinter()
logging.basicConfig(format='%(asctime)s: %(levelname)s %(message)s', level=logging.INFO)

LightSetting = collections.namedtuple('LightSetting', ['command','timeout'])

BRIDGE_IP = '192.168.1.15'
LIGHT_GROUP = 'Living Room'

LOOP_DELAY = 1
DAY_TIMEOUT = 900
NIGHT_TIMEOUT = 180
WU_API_KEY = 'Weather Underground API key here'
ZIP_CODE = 'Zip Code here'

MORNING_COMMAND  = {'ct' : 153, 'bri' : 202, 'on' : True}
EVENING_COMMAND = {'ct' : 328, 'bri' : 254, 'on' : True}
NIGHT_COMMAND  = {'ct' : 328, 'bri' : 127, 'on' : True}

weather = None

def refresh_weather():
	global weather
	f = urllib2.urlopen('http://api.wunderground.com/api/' + WU_API_KEY + 
	                    '/astronomy/conditions/q/' + ZIP_CODE + '.json')
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
		return None
		
	check_time = now.replace(hour=22, minute=30, second=0)
	if now < check_time:
		return LightSetting(command = EVENING_COMMAND, timeout = DAY_TIMEOUT)
	else:
		return LightSetting(command = NIGHT_COMMAND, timeout = NIGHT_TIMEOUT)
	
    
def all_on(command):
	logging.info('Lights on')
	bridge.set_group(LIGHT_GROUP, command)

def all_off():
	logging.info('Lights off')
	bridge.set_group(LIGHT_GROUP, 'on', False)
	
def motion_detected():
	return io.input(PIR_PIN)

# Set up the pin we'll be reading the PIR on
io.setmode(io.BCM)
io.setup(PIR_PIN, io.IN)         
	
# Connect to the hue bridge
try:
	bridge = phue.Bridge(BRIDGE_IP)
except Exception as e:
	print "Unable to connect to hue bridge."
	print e
	exit(1)

light_timer = None
light_setting = None

refresh_weather()

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