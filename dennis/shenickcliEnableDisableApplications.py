############################################################################
#THIS SCRIP ENABLES/DISABLES ALL OR LISTS OF SHENICK APPLICATIONS
############################################################################
import paramiko
import time
import sys
applist2 = []
appidlist = []
appidtemplist = []
compositelist = []
enablelist = []
disablelist = []


###############################################################################
#APPLICATIONS TO BE ENABLED SHOULD BE CONTAINED IN THE LIST NAMED enablelist
#APPLICATIONS TO BE DISABLED SHOULDBE CONTAINED IN THE LIST NAMED disablelist
#TO ENABLE ALL APPLICATIONS, SET THE adminState variable to a value of "ENALL"
#TO DISABLE ALL APPLICATIONS, SET THE adminState variable to a value of "DISALL"


adminState = "ENALL"
enablelist = ["httpclt4-01","httpclt3-45","httpclt3-08"]
#disablelist = ["httpclt4-01","httpclt3-45","httpclt3-08"]


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
def en_dis_all():
    for lstdex, elem in enumerate(appidlist):
      remote_conn.send("cli setAdminStateOfApplications "+(elem)+" "+(adminall)+"\n")
      print("cli setAdminStateOfApplications "+(elem)+" " +(adminall)+"\n")


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



if adminState.upper() == "ENALL":
    adminall = "'Enabled'"
    en_dis_all()
if adminState == "DISALL":
    adminall = "'Disabled'"
    en_dis_all()


      
#THE FOLLOWING SETS THE APPLICATIONS LIST PROVIDED IN THE disablelist TO DISABLED.

if len(disablelist) > 0:
    for lstdex, theappname in enumerate(disablelist):
        for dex, theappid in enumerate(appidlist):
            if theappname in theappid:
                remote_conn.send("cli setAdminStateOfApplications "+(theappid)+" 'Disabled'\n")
                output =remote_conn.recv(1000)
                time.sleep(.2)
                
#THE FOLLOWING SETS THE APPLICATIONS LIST PROVIDED IN THE enablelist TO ENABLED.
if len(enablelist) > 0:
    for lstdex, theappname in enumerate(enablelist):
        for dex, theappid in enumerate(appidlist):
            if theappname in theappid:
                print(theappid)
                remote_conn.send("cli setAdminStateOfApplications "+(theappid)+" 'Enabled'\n")
                output =remote_conn.recv(1000)
                time.sleep(.2)


#################################################################################################################

