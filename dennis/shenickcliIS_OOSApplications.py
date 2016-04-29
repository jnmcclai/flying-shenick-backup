############################################################################
#THIS SCRIP SETS THE SERVICE STATE OF  ALL OR LISTS OF SHENICK APPLICATIONS
#TO IN SERVICE OR OUT OF SERVICE
############################################################################
import paramiko
import time
import sys
applist2 = []
appidlist = []
appidtemplist = []
compositelist = []
inservicelist = []
outservicelist = []


###############################################################################
#APPLICATIONS TO BE PUT IN SERVICE SHOULD BE CONTAINED IN THE LIST NAMED inservicelist
#APPLICATIONS TO BE DISABLED SHOULDBE CONTAINED IN THE LIST NAMED out of servicelist
#TO PUT ALL APPLICATIONS IN SERVICE, SET THE srvstate variable to a value of "ISALL"
#TO PUT ALL APPLICATIONS OOS, SET THE srvstate variable to a value of "OOSALL"


srvstate = "NULL"
inservicelist = ["httpclt4-01","httpclt3-45","httpclt3-08"]
#outservicelist = ["httpclt4-01","httpclt3-45","httpclt3-08"]


##############################################################################
#THE FOLLOWING LINES ARE LIKELY NOT NEEDED.  THE CHASSIS CONNECTION IS
#LIKELY VIA ANOTHER MODULE
ip = '10.13.225.38'
username = 'cli'
password = 'diversifEye'
remote_conn_pre=paramiko.SSHClient()
remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
remote_conn_pre.connect(ip,username=username,password=password)

#################################################################
# THE TEST GROUP IS DEFINED HERE.  IT IS ANTICIPATED THAT THIS MIGHT BE INPUT
# FROM THE CALLING PROCEDURE
testgroup = "//OSP_ERPS_Stateful-OSP-COT"

##########################################################################
def is_oos_all():
    for lstdex, elem in enumerate(appidlist):
      remote_conn.send("cli setServiceStateOfApplications "+(elem)+" "+(srvstateall)+"\n")
      print("cli setServiceStateOfApplications "+(elem)+" " +(srvstateall)+"\n")


#################################################################################################################


remote_conn=remote_conn_pre.invoke_shell()
output=remote_conn.recv(2000)

remote_conn.send("cli configure cliDefaultDiversifEyeUser=osp\n")
##########################################################################
sys.stdout.flush()
time.sleep(1)
remote_conn.send("cli getAppIds //OSP_ERPS_Stateful-OSP-COT %\n")
time.sleep(3)
#########################################################################
#The number of output bytes received is defined here.  This might need to 
#be tunded depending on the number of applications that are to be listed.
output = remote_conn.recv(20000)


time.sleep(1)
appidtemplist = output.split("\r\n")
for lstdex, elem in enumerate(appidtemplist):
    string_test_var = elem
    if "//" in elem and string_test_var.startswith("//"):
        appidlist.append(elem)

time.sleep(.1)
compositelist = []



if srvstate.upper() == "ISALL":
    srvstateall = "'In Service'"
    is_oos_all()
if srvstate == "OOSALL":
    srvstateall = "'Out of Service'"
    is_oos_all()


      
#THE FOLLOWING SETS THE APPLICATIONS LIST PROVIDED IN THE disablelist TO DISABLED.

if len(outservicelist) > 0:
    for lstdex, theappname in enumerate(outservicelist):
        for dex, theappid in enumerate(appidlist):
            if theappname in theappid:
                remote_conn.send("cli setServiceStateOfApplications "+(theappid)+" 'Out of Service'\n")
                output =remote_conn.recv(1000)
                time.sleep(.2)
                
#THE FOLLOWING SETS THE APPLICATIONS LIST PROVIDED IN THE enablelist TO ENABLED.
if len(inservicelist) > 0:
    for lstdex, theappname in enumerate(inservicelist):
        for dex, theappid in enumerate(appidlist):
            if theappname in theappid:
                print(theappid)
                remote_conn.send("cli setServiceStateOfApplications "+(theappid)+" 'In Service'\n")
                output =remote_conn.recv(1000)
                time.sleep(.2)


#################################################################################################################

