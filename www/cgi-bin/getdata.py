#!/usr/bin/python
from __future__ import division
import cgi
import cgitb
cgitb.enable()

from time import time
from datetime import datetime

import sqlite3
import json

def query(c, q):
	c.execute(q)
	data = []
	for row in c:
		data.append(list(row))
	return data

def provide(params):
	conn = sqlite3.connect('../../datalogs/weather.sqlite')
	c = conn.cursor()

	sensor_id = 1
	if params['sensor'] == 2:
		sensor_id = 2

	table = "daily"
	timedelta = 30*24*3600
	format = "%d"
	if params['res'] == 1:
		table = "hourly"
		timedelta = 72*3600
		format = "%H"
	if params['res'] == 2:
		table = "minutely"
		timedelta = 12*3600
		format = "%H.%M"

	stop = time()
	start = stop - timedelta

	if params['start'] > 0:
		start = params['start']

	if params['stop'] > 0:
		stop = params['stop']

	def query_data(cursor, table, fields, sensor, start, stop):
		fields.insert(0, "timestamp")
		fields_str = ",".join(fields)
		where_str = "sensor_id=%d" % (sensor)
		if start:
			where_str += " AND timestamp > %d" % (start)
		if stop:
			where_str += " AND timestamp < %d" % (stop)

		q = 'SELECT %s FROM %s WHERE %s ORDER BY timestamp ASC' % (fields_str, table, where_str)
		return cursor.execute(q)

	if params["maxmin"] > 0:
		q = query_data(c, table, ["value", "max", "min"], params["sensor"], start, stop)

		data_min = []
		data_val = []
		data_max = []
		for row in q:
			(ts, vval, vmax, vmin) = row
			# Javascript uses unix timestamp in milliseconds:
			ts = ts * 1000
			data_min.append( [ts, vmin] )
			data_val.append( [ts, vval] )
			data_max.append( [ts, vmax] )

		print json.dumps({'values' : [data_val], 'bands' : [data_min, data_max]}, indent=1)

	else:
		q = query_data(c, table, ["value"], params["sensor"], start, stop)

		data = []
		for (ts, val) in q:
			# Javascript uses unix timestamp in milliseconds:
			data.append( [ts*1000, val] )

		print json.dumps({'values' : [data]}, indent=1)



input_data = cgi.FieldStorage()

# Disable cache
print "Cache-Control: no-cache, must-revalidate"
print "Expires: Sat, 26 Jul 1997 05:00:00 GMT"
# Required header that tells the browser how to render the text.
print "Content-Type: text/plain\n\n"

# Set default parameters
params = { 'sensor' : 1,
	'res' : 0,
	'start' : 0,
	'stop' : 0,
	'maxmin' : 0,
	}

for name in input_data.keys():
	if params.has_key(name):
		val = input_data[name].value
		params[name] = int(val)

data = provide(params)
