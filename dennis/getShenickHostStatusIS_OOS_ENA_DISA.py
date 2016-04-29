#THIS SCRIPT GETS SHENICK HOST STATUS INFORMATION.  THE USER PROVIDES THE TEST
#GROUP AND APPLICATION NAME LIST AS AN INPUT
#################################################################################
import paramiko
import time
import sys
hoststat_list = []
hostname_list = []
input_hostname_list = []

#########################################################################
#THIS IS THE APPNAME LIST PROVIDED BY THE USER
input_hostname_list = ["httpclt2-8","httpclt2-21","httpclt1-18", "httpclt2-4"]
#########################################################################

##########################################################################
#THE FOLLOWING LINES ARE LIKELY NOT NEEDED.  THE CHASSIS CONNECTION IS
#LIKELY VIA ANOTHER MODULE
ip = '10.13.225.38'
username = 'cli'
password = 'diversifEye'
remote_conn_pre=paramiko.SSHClient()
remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
remote_conn_pre.connect(ip,username=username,password=password)

#########################################################################
# THE TARGET TEST GROUP IS ANTICIPATED TO BE PROVIDED VIA ANOTHER
# PROCEDURE.  
testgroup = "'//OSP_ERPS_Stateful-OSP-COT'"


#########################################################################

remote_conn=remote_conn_pre.invoke_shell()
output=remote_conn.recv(2000)
sys.stdout.flush()
#########################################################################
#SHENICK USER IS HARD CODED HERE.  THIS LINE MAY NOT BE NECESSARY
remote_conn.send("cli configure cliDefaultDiversifEyeUser=osp\n")
#########################################################################

sys.stdout.flush()
remote_conn.send("cli listHosts "+(testgroup)+"\n")
time.sleep(3)
var_hoststat = remote_conn.recv(10000)
temp_hoststat_list = var_hoststat.split("\r\n")

for lstdex, elem in enumerate(temp_hoststat_list):
  if "IP/" in elem:
    elem = elem.strip("IP/")
    hostname = elem.split(" ")
    hostname = hostname[0]
    hoststat_list.append(elem)
    hostname_list.append(hostname)

for dex, hstname in enumerate(input_hostname_list):
  for dex2, hoststat in enumerate(hoststat_list):
    statname = hoststat.split(" ")
    statname = statname[0]
    if hstname == statname:
        print(hoststat)
        break
  
  






