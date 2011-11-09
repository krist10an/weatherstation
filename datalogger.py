
import sys
import time
import serial

from collector import *

def parse_from_serial(line):
	try:
		(hpa, t) = line.split(";")
		hpa = float(hpa)
		t = float(t)
		return (time.time(), hpa, t)
	except:
		pass

	return None

def parse_from_file(line):
	try:
		(ts, press, temp) = line.split(";")
		ts = int(ts)
		press = float(press)
		temp = float(temp)

		return (ts, press, temp)
	except:
		pass
		return None

def import_weather(filename, w):

	f = open(filename)
	count = 0
	for line in f:
		(ts, press, temp) = parse_from_file(line)

		w.add_temperature(ts, temp)
		w.add_pressure(ts, press)
		count += 1

	f.close()
	return count


def read_csv(ws, input_csv_file):

	start = time.time()
	before = ws.get_count()

	count = import_weather(input_csv_file, ws)

	after = ws.get_count()
	elapsed = (time.time() - start)

	print "Parsed %d lines in %.1f sec" % (count, elapsed)
	print "Added %d-%d-%d" % ((after[0]-before[0]), (after[1]-before[1]), (after[2]-before[2]))
	print "Total %d-%d-%d" % (after[0], after[1], after[2])

def read_serial(ws, output_file):
	ser = serial.Serial('/dev/ttyACM0', 9600)
	while 1:
		line = ser.readline()

		try:
			(tid, hpa, t) = parse_from_serial(line)

			f = open(output_file , "a+w")
			outline = "%d ; %f ; %f \n" % (tid, hpa, t)
			f.write(outline)
			f.close()

			ws.add_pressure(tid, hpa)
			ws.add_temperature(tid, t)

			print outline
		except TypeError:
			pass

if __name__=="__main__":
	output_file = "datalogs/weather.csv"
	output_db = "datalogs/weather.sqlite"

	ws = WeatherStation(output_db)
	read_csv(ws, output_file)
	read_serial(ws, output_file)
