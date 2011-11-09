from __future__ import division
import sqlite3
from math import floor
import logging

class Collector(object):
	def __init__(self, timescale, propagate_minmax=True):
		self.timescale = timescale
		self.data = []

		self.value_sum = 0
		self.value_count = 0
		self.value_min = float("inf")
		self.value_max = 0

		self.last_ts = 0
		self.last_ts_div = 0

		self.overflow_object = None
		self.propagate_minmax = propagate_minmax

		logging.basicConfig(filename='datalogs/collector.log',level=logging.DEBUG)
		if 1:
			self.logger = logging.getLogger("collector")
		else:
			self.logger = None

	def log(self, str):
		if self.logger:
			self.logger.debug(str)
			
	def add_value(self, timestamp, value):
		ts_div = floor(timestamp / self.timescale)

		if self.last_ts == 0:
			self.last_ts = timestamp
			self.last_ts_div = ts_div
			self.value_count += 1
			self.value_sum += value

		if value < self.value_min:
			self.value_min = value

		if value > self.value_max:
			self.value_max = value

		# Error checking
		if self.last_ts_div > ts_div:
			raise Exception("Need timestamp to be monotonic")

		if self.last_ts_div < ts_div:
			# Next timestamp found, save previous values
			# Save value at overflow time (ts)
			# (Since it contains the data from last_ts to ts)
			if self.value_count > 0:
				timestamp_floor = ts_div * self.timescale
				avg = self.value_sum / self.value_count

				self.log("Add value %d: %f, %f, %f" % (timestamp_floor, avg, self.value_min, self.value_max))
				self.store_value(timestamp_floor, avg, self.value_min, self.value_max)
				self.overflow(timestamp_floor, avg, self.value_min, self.value_max)
			else:
				self.log("Error addin value %d: %f, value_count=0 => skipping" % (timestamp, value))

			self.value_sum = 0
			self.value_count = 0
			self.last_ts_div = ts_div
			self.value_min = float("inf")
			self.value_max = 0

		else:
			# Accumulate samples within the same timescale
			self.value_count += 1
			self.value_sum += value

	def store_value(self, ts, val, vmin, vmax):
		print "Store",self.timescale, ts, val, vmin, vmax

	def set_overflow_object(self, obj):
		if isinstance(obj, Collector):
			self.overflow_object = obj
		else:
			raise Exception("I only support Collector objects")

	def overflow(self, ts, val, min, max):
		if self.overflow_object:
			self.log("Overflow %d: v=%f min=%f max=%f" % (ts, val, min, max))

			# Propagate max/min values
			if self.propagate_minmax:
				if min < self.value_min:
					self.value_min = min
				if max > self.value_max:
					self.value_max = max

			self.overflow_object.add_value(ts, val)

class DatabaseCollector(Collector):
	def __init__(self, timescale, db_connector, tablename, sensor_id, propagate_minmax=True):
		super(DatabaseCollector, self).__init__(timescale, propagate_minmax)
		self.db_connector = db_connector
		self.tablename = tablename
		self.sensor_id = sensor_id

		self.cursor = self.db_connector.cursor()
		try:
			self.log("Create table %s " % (tablename))
			# Create table
			query = "CREATE TABLE %s (" % (tablename)
			query += "  timestamp INTEGER, "
			query += "  sensor_id INTEGER, "
			query += "  value REAL, "
			query += "  max REAL, "
			query += "  min REAL, "
			query += "PRIMARY KEY (timestamp, sensor_id))"
			self.log("Query: "+query)

			self.cursor.execute(query)
			self.log("Create table ok")
		except sqlite3.OperationalError:
			# Table already exist
			self.log("Create table failed, table exists")
			pass

	def log(self, str):
		if self.logger:
			self.logger.debug("%s - %d : %s" % (self.tablename, self.sensor_id, str))

	def store_value(self, ts, val, vmin, vmax):
		try:
			self.cursor.execute("INSERT INTO %s (timestamp, sensor_id, value, min, max) VALUES (%d, %d, %f, %f, %f)" % 
					(self.tablename, ts, self.sensor_id, val, vmin, vmax))
			self.db_connector.commit()
			self.log("Stored %d in db" % (ts))

		except sqlite3.IntegrityError:
			# Value already exists, nothing needs to be done.
			self.log("Value %d exists in db" % (ts))
			pass

class WeatherStation(object):
	def __init__(self, dbfile):
		self.db = sqlite3.connect(dbfile)
		self.cursor = self.db.cursor()

		self.tcoll_min  = DatabaseCollector(10*60,   self.db, "minutely", 1, False) # Every ten minutes
		self.tcoll_hour = DatabaseCollector(3600,    self.db, "hourly", 1)   # Every hour
		self.tcoll_day  = DatabaseCollector(24*3600, self.db, "daily",  1)   # Every day

		self.tcoll_min.set_overflow_object(self.tcoll_hour)
		self.tcoll_hour.set_overflow_object(self.tcoll_day)

		self.pcoll_min  = DatabaseCollector(10*60,   self.db, "minutely", 2, False) # Every ten minutes
		self.pcoll_hour = DatabaseCollector(3600,    self.db, "hourly", 2)   # Every hour
		self.pcoll_day  = DatabaseCollector(24*3600, self.db, "daily",  2)   # Every day

		self.pcoll_min.set_overflow_object(self.pcoll_hour)
		self.pcoll_hour.set_overflow_object(self.pcoll_day)

	def __del__(self):
		self.db.close()

	def add_temperature(self, ts, value):
		self.tcoll_min.add_value(ts, value)

	def add_pressure(self, ts, value):
		self.pcoll_min.add_value(ts, value)

	def get_count(self):
		def q(table):
			self.cursor.execute('SELECT COUNT(*) FROM %s' % (table))
			row = self.cursor.fetchone()
			if row and row[0]:
				return row[0]
			return 0

		m = q('minutely')
		h = q('hourly')
		d = q('daily')

		return (m, h, d)
