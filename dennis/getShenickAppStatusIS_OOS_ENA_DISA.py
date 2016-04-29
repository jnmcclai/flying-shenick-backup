#THIS SCRIPT GETS SHENICK APPLICATION STATUS INFORMATION.  THE USER PROVIDES THE TEST
#GROUP AND APPLICATION NAME LIST AS AN INPUT
#################################################################################
import paramiko
import time
import sys
appstat_list = []
appname_list = []
input_appname_list = []

#########################################################################
#THIS IS THE APPNAME LIST PROVIDED BY THE USER
input_appname_list = ["httpclt1-21","httpclt4-04"]
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
remote_conn.send("cli listApplications "+(testgroup)+"\n")
#time.sleep(3)
var_appstat = remote_conn.recv(10000)
temp_appstat_list = var_appstat.split("\r\n")

for lstdex, elem in enumerate(temp_appstat_list):
  if "IP/" in elem:
    elem = elem.strip("IP/")
    appname = elem.split(" ")
    appname = appname[0]
    appstat_list.append(elem)
    appname_list.append(appname)

for dex, apname in enumerate(input_appname_list):
  for dex2, appstat in enumerate(appstat_list):
    statname = appstat.split(" ")
    statname = statname[0]
    if apname == statname:
        print(appstat)
        break
  
  






