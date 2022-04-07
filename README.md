# modemstats
Openreach HG612 Stats to InfluxDB 2


# environment variables

db_url = os.getenv('db_url','localhost:8086')
db_token = os.getenv('db_token','')
db_org = os.getenv('db_org','organisation')
db_bucket = os.getenv('db_bucket','modemstats')

modem_ip = os.getenv('modem_ip','192.168.100.1')
modem_username = os.getenv('modem_username','admin')
modem_password = os.getenv('modem_password','admin')
