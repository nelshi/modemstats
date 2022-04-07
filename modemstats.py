#!/usr/bin/python
import telnetlib as tn
import time as t
import datetime as dt
import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
import sdnotify
from configparser import ConfigParser
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

## Database Information

db_url = os.getenv('db_url','localhost:8086')
db_token = os.getenv('db_token','')
db_org = os.getenv('db_org','organisation')
db_bucket = os.getenv('db_bucket','modemstats')

## Modem Information

modem_ip = os.getenv('modem_ip','192.168.100.1')
modem_username = os.getenv('modem_username','admin')
modem_password = os.getenv('modem_password','admin')

##

client = InfluxDBClient(url=db_url, token=db_token, org=db_org)

write_api = client.write_api(write_options=SYNCHRONOUS)

def init_db():
    pass

##

class ParsedStats:
    def __init__(self, conn_stats_output, system_uptime):
        conn_stats_output_split = conn_stats_output.decode().split("\r\n")
        #print(conn_stats_output_split)
        if len(conn_stats_output_split) == 118:
            self.connection_up = True
            interleavedepth_line = conn_stats_output_split[28].replace("D:\t\t","")
            interleavedepth_split = interleavedepth_line.split("\t\t")
            self.interleavedepth = int(interleavedepth_split[0])
            interleaving_line = conn_stats_output_split[54].replace("INP:\t\t", "")
            interleaving_split = interleaving_line.split("\t\t")
            self.interleaving = float(interleaving_split[0])
            delay_line = conn_stats_output_split[56].replace("delay:\t\t","")
            delay_split = delay_line.split("\t\t")
            self.delay = float(delay_split[0])
            fecerror_line = conn_stats_output_split[82].replace("FEC:\t\t","")
            fecerror_split = fecerror_line.split("\t\t")
            self.fecerror = int(fecerror_split[0])
            max_line = conn_stats_output_split[5].replace("Max:\tUpstream rate = ", "")
            max_split = max_line.split(", Downstream rate = ")
            self.max_up = int(max_split[0].replace(" Kbps", ""))
            self.max_down = int(max_split[1].replace(" Kbps", ""))
            current_line = conn_stats_output_split[6].replace("Bearer:\t0, Upstream rate = ", "")
            current_split = current_line.split(", Downstream rate = ")
            self.current_up = int(current_split[0].replace(" Kbps", ""))
            self.current_down = int(current_split[1].replace(" Kbps", ""))
            snr_line = conn_stats_output_split[16].replace("SNR (dB):\t ", "")
            snr_split = snr_line.split("\t\t ")
            self.snr_down = float(snr_split[0])
            self.snr_up = float(snr_split[1])
            attn_line = conn_stats_output_split[17].replace("Attn(dB):\t ", "")
            attn_split = attn_line.split("\t\t ")
            self.attn_down = float(attn_split[0])
            self.attn_up = float(attn_split[1])
            pwr_line = conn_stats_output_split[18].replace("Pwr(dBm):\t ", "")
            pwr_split = pwr_line.split("\t\t ")
            self.pwr_down = float(pwr_split[0])
            self.pwr_up = float(pwr_split[1])
            err_secs_line = conn_stats_output_split[48].replace("ES:\t\t", "")
            err_secs_split = err_secs_line.split("\t\t")
            self.err_secs_up = int(err_secs_split[0])
            self.err_secs_down = int(err_secs_split[1])
            serious_err_secs_line = conn_stats_output_split[49].replace("SES:\t\t", "")
            serious_err_secs_split = serious_err_secs_line.split("\t\t")
            self.serious_err_secs_up = int(serious_err_secs_split[0])
            self.serious_err_secs_down = int(serious_err_secs_split[1])
            unavailable_secs_line = conn_stats_output_split[50].replace("UAS:\t\t", "")
            unavailable_secs_split = unavailable_secs_line.split("\t\t")
            self.unavailable_secs_up = int(unavailable_secs_split[0])
            self.unavailable_secs_down = int(unavailable_secs_split[1])
            self.available_secs = int(conn_stats_output_split[51].replace("AS:\t\t", ""))
        else:
            self.connection_up = False
        system_uptime_split = system_uptime.decode().split("\r\n")
        self.system_uptime = float(system_uptime_split[1].split(" ")[0])

##

def main():
    init_db()  # Setup the database if it does not already exist.
    
    while True:
        timestamp = dt.datetime.fromtimestamp(t.time()).strftime("%Y-%m-%dT%H:%M:%S")
        print('Attempting to retrieve stats at:')
        print(timestamp)
        try:
            parsed_stats = retrieve_stats()
            modemstats(parsed_stats, timestamp)
        except Exception as ex:
            ex_type, value, traceback = sys.exc_info()
            filename = os.path.split(traceback.tb_frame.f_code.co_filename)[1]
            logger.error("{0}, {1}: {2}".format(filename, traceback.tb_lineno, ex))
        t.sleep(60)

##

def retrieve_stats():
    try:
        tnconn = tn.Telnet(modem_ip)
        tnconn.read_until(b"Login:")
        tnconn.write("{0}\n".format(modem_username).encode())
        tnconn.read_until(b"Password:")
        tnconn.write("{0}\n".format(modem_password).encode())
        tnconn.read_until(b"ATP>")
        tnconn.write(b"sh\n")
        tnconn.read_until(b"#")
        tnconn.write(b"xdslcmd info --stats\n")
        stats_output = tnconn.read_until(b"#")
        tnconn.write(b"cat /proc/uptime\n")
        system_uptime = tnconn.read_until(b"#")
        parsed_stats = ParsedStats(stats_output, system_uptime)
        return parsed_stats
    except Exception:
        raise

##

def format_json(parsedStats, timestamp):
    try:
        if parsedStats.connection_up:
            return [{"measurement": "connection", "time": timestamp,
                     "fields":
                         {"AttDown": parsedStats.attn_down,
                          "AttnUp": parsedStats.attn_up,
                          "AvailableSecs": parsedStats.available_secs,
                          "CurrDown": parsedStats.current_down,
                          "CurrUp": parsedStats.current_up,
                          "ErrSecsDown": parsedStats.err_secs_down,
                          "ErrSecsUp": parsedStats.err_secs_up,
                          "MaxDown": parsedStats.max_down,
                          "MaxUp": parsedStats.max_up,
                          "PwrDown": parsedStats.pwr_down,
                          "PwrUp": parsedStats.pwr_up,
                          "SeriousErrSecsDown": parsedStats.serious_err_secs_down,
                          "SeriousErrSecsUp": parsedStats.serious_err_secs_up,
                          "SNRDown": parsedStats.snr_down,
                          "SNRUp": parsedStats.snr_up,
                          "SystemUptime": parsedStats.system_uptime,
                          "UnavailableSecsDown": parsedStats.unavailable_secs_down,
                          "UnavailableSecsUp": parsedStats.unavailable_secs_up,
                          "InterleaveDepth": parsedStats.interleavedepth,
                          "Interleaving": parsedStats.interleaving,
                          "Delay":parsedStats.delay,
                          "FECError":parsedStats.fecerror
                          }}]
        else:
            return [{"measurement": "connection", "time": timestamp,
                     "fields":
                         {"AttDown": -1,
                          "AttnUp": -1,
                          "AvailableSecs": -1,
                          "CurrDown": -1,
                          "CurrUp": -1,
                          "ErrSecsDown": -1,
                          "ErrSecsUp": -1,
                          "MaxDown": -1,
                          "MaxUp": -1,
                          "PwrDown": -1,
                          "PwrUp": -1,
                          "SeriousErrSecsDown": -1,
                          "SeriousErrSecsUp": -1,
                          "SNRDown": -1,
                          "SNRUp": -1,
                          "SystemUptime": parsedStats.system_uptime,
                          "UnavailableSecsDown": -1,
                          "UnavailableSecsUp": -1,
                          "InterleaveDepth": -1,
                          "Interleaving": -1,
                          "Delay": -1,
                          "FECError": -1
                          }}]
    except Exception:
        raise

##

def modemstats(parsed_stats, timestamp):
    data_json = format_json(parsed_stats, timestamp)
    try:
        write_api.write(bucket=db_bucket, org=db_org, record=data_json)
        client.close()
        print('Recorded stats to database.')
        print(timestamp)
    except Exception:
        print('Database connection failed.')
        raise

##

n = sdnotify.SystemdNotifier()
n.notify("READY=1")

#config_path = "config.ini"

#config = ConfigParser()
#config.read(config_path)

#if "InfluxDB" in config:
#    db_url = config["InfluxDB"].get("url")
#    db_token = config["InfluxDB"].get("token")
#    db_org = config["InfluxDB"].get("org")
#    db_bucket = config["InfluxDB"].get("bucket")
#else:
#    raise Exception("Wasn't able to find the 'InfluxDB' section in the config")

#if "Modem" in config:
#    modem_ip = config["Modem"].get("ip-address")
#    modem_username = config["Modem"].get("username")
#    modem_password = config["Modem"].get("password")
#else:
#    raise Exception("Wasn't able to find the 'Modem' section in the config")
#
#if modem_ip is None or modem_username is None or modem_password is None:
#    raise Exception("At least one piece of Modem connection information is missing from the config")

logger = logging.getLogger("Rotating Error Log")
logger.setLevel(logging.ERROR)
handler = logging.FileHandler('errorlog.log')
formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
main()