import Shenick_Analysis as Shenick_Analysis
#import zipfile
import math
import os

#  Program defaults, for now hard-code the Shenick P/F parameters and script information


#  Instantiate Shenick_Analysis.  This should open a SSH session to the Shenick

Shenick = Shenick_Analysis(tvmcIp='10.13.225.18', tvmUser='IPTV', partition=2, testGroup='//GPON/GPON_IGMP_Only_LoadTest')


   # def __init__(self, tvmcIp, chassisType='5500', tvmUser= 'adtran', partition = 1):
#  Download the .xml script from Web.pq.adtran.com


#  Change XML run-time parameter


#  Upload xml file to the Shenick.


#  Optional, enable/disable applications.  This is a placeholder for a Pythonn call


#  Start script


#  Run for test time, here a simple sleep command


#  Stop script


#  Get results, zip to local box (PC in this case)


#  Unzip the file.


#  Run R program using ADTRAN.R.  Probably need to use TRY/EXCEPT on load to verify R is on the local box


#  Analyze IGMP Client results


#  Analyze HTTP Client results.


#  Close SSH session