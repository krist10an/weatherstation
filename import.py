from __future__ import division

from collector import *
from datalogger import *

if __name__=="__main__":
	output_file = "datalogs/weather.csv"
	output_db = "datalogs/weather_hurra.sqlite"

	ws = WeatherStation(output_db)
	read_csv(ws, output_file)
