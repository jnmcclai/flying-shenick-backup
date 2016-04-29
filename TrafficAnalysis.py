from   robot.libraries.Telnet  import Telnet
from   robot.libraries.BuiltIn import BuiltIn
import re
import os
import time
import robot
import string
import datetime
from ftplib import FTP
import csv
import os.path
import ShenickCli
import sys
import WindowProvUtils
from robot.api import logger

class TrafficAnalysis:
    """
    Library for analysing the traffic

    *Parameters* : None

    *Returns* : None
    """
    def __init__(self):
        self.cmnObj = WindowProvUtils.WindowProvUtils()


#  Program defaults, for now hard-code the Shenick P/F parameters and script information

#  Download the .xml script from Web.pq.adtran.com

#  Change XML run-time parameter

#  Upload xml file to the Shenick.

    def copyFileFromServer(self, paramDict):
        """
        This method gets the file from remote server and copy to given local file path.

        *Parameters* :
        - paramDict : <Dictionary> ; dictionary contains key, value pair . possible values are
        | *Key* | *Value* | *Comment* |
        | *serverIp* | <string> | IpAddress of the server from which getting the files |
        | *userName* | <string> | Username to login the server |
        | *password* | <string> | Password to login the server |
        | *sourceFilePath* | <string> | Path of the file to be copied from ftp server. Ex: /home/cli/IPTV/IPTV.zip |
        | *destFilePath* | <string> | Location of the destination path i.e where we want to save the file in local machine. Ex: C:/diversifEyeClient/analysis/bin/IPTV.zip |

        *Returns* : None
        """
        self.cmnObj.copyFileFromServer(paramDict)

    def runAnalysisBatchFile(self, resultsFilePath, outputPath):
        """
        This method runs Analyse.bat on give results (*.zip) and saves the summary csv files in given output path.

        *Parameters* :
        - *resultsFilePath*  : <string> ; Path to results zip file, ex: C:\\diversifEyeClient\\analysis\\bin\\IPTV.Zip
        - *outputPath*      : <string> ; Path to save the output summary results files. ex: C:\\diversifEyeClient

        *Returns* : None
        """
        self.cmnObj.runAnalysisBatchFile(resultsFilePath, outputPath)

    def evaluateIgmpApplications(self, paramDict):
        """
        This method read Summary_Multicast_Client.csv file and evaluate all IGMP applications, which includes MOS and Zapping applications.

        *Parameters* :
        - paramDict : <Dictionary> ; dictionary contains key, value pair . possible values are
        | *Key* | *Value* | *Comment* |
        | *csvFilePath* | <string> | Path to Summary_Multicast_Client.csv file. Ex: C:\\diversifEyeClient\\IPTV\\output\\Miscellaneous\\Summary_Multicast_Client.csv
        | *mosAppType* | <string> | MOS measured application string search type. Ex: VQA |
        | *zapAppType* | <string> | Zapping measured application string search type. Ex: Zap |
        | qmVideoMOSLimit | <float> | QmVideoMos Limit. Default value is 4 |
        | imparedFramesLimit | <integer> | Impared Frame Count Limit. Default value is 3 |
        | droppedPacketsLimit | <integer> | Dropped packets Limit, default value is 20 |
        | joinTimeAvgLimit | <float> | Mean Join Time Average Limit, default value is 125 |
        | joinPercLimit | <float> | Percentage of Joins Completed Vs Joins Initiated, Limit, default value is 0.95 |
        | leavePerLimit | <float> | Percentage of Leaves Completed Vs Leaves Initiated, Lim, default value is 0.95 |
        | zapPerLimit | <float> | Percentage of Leaves Completed Vs Joins Completed, Limi, default value is 0.95 |

        *Returns* : None
        """


#------>if type(paramDict) is not dict:
        if not paramDict:
            raise AssertionError('paramDict is not dictionary')
        elif not paramDict:
            raise AssertionError('paramDict is empty')

        manDateParams = ['csvFilePath', 'mosAppType', 'zapAppType']
        for param in manDateParams:
            if param not in paramDict.keys():
                raise AssertionError('evaluateIgmpApplications: %s is not provided in argument list which is manadatory arguement' % param)

        if not paramDict.has_key('qmVideoMOSLimit') or paramDict['qmVideoMOSLimit'] == '':
            paramDict['qmVideoMOSLimit'] = 4

        if not paramDict.has_key('imparedFramesLimit') or paramDict['imparedFramesLimit'] == '':
            paramDict['imparedFramesLimit'] = 3

        if not paramDict.has_key('droppedPacketsLimit') or paramDict['droppedPacketsLimit'] == '':
            paramDict['droppedPacketsLimit'] = 20

        if not paramDict.has_key('joinTimeAvgLimit') or paramDict['joinTimeAvgLimit'] == '':
            paramDict['joinTimeAvgLimit'] = 125

        if not paramDict.has_key('joinPercLimit') or paramDict['joinPercLimit'] == '':
            paramDict['joinPercLimit'] = 0.95

        if not paramDict.has_key('leavePerLimit') or paramDict['leavePerLimit'] == '':
            paramDict['leavePerLimit'] = 0.95

        if not paramDict.has_key('zapPerLimit') or paramDict['zapPerLimit'] == '':
            paramDict['zapPerLimit'] = 0.95

        resultStatus = "PASS"

        print paramDict['qmVideoMOSLimit']
        logger.warn(paramDict['qmVideoMOSLimit'])

        with open(paramDict['csvFilePath']) as csvfile:
            for row in csv.DictReader(csvfile):
                ipAddress = str(row['IP Address']).split('/', 1)[0]
                if ipAddress != '0.0.0.0':
                    # Evaluate VQA Statistics #
                    if re.match('.*' + paramDict['mosAppType'] + '.*', row['Entity Name'], re.IGNORECASE):
                        # Evaluate VQA MOS #
                        if float(row['Mean QmVideo MOS']) >= float(paramDict['qmVideoMOSLimit']):
                            print 'PASS :: ' + '<' + row['Entity Name'] + '> ' + 'MOS ' + str(row['Mean QmVideo MOS']) + ' was greater than or equal to ' +  str(paramDict['qmVideoMOSLimit'])
                        else:
                            print 'FAIL :: ' + '<' + row['Entity Name'] + '> ' + 'MOS ' + str(row['Mean QmVideo MOS']) + ' was less than ' +  str(paramDict['qmVideoMOSLimit'])
                            resultStatus = 'FAIL'
                        # Evaluate VQA Dropped Packets #
                        if int(row['Dropped Packets']) <= int(paramDict['droppedPacketsLimit']):
                            print 'PASS :: ' + '<' + row['Entity Name'] + '> ' + 'Total packet loss ' + str(row['Dropped Packets']) + ' was less than or equal to ' +  str(paramDict['droppedPacketsLimit'])
                        else:
                            print 'FAIL :: ' + '<' + row['Entity Name'] + '> ' + 'Total packet loss ' + str(row['Dropped Packets']) + ' was greater than ' +  str(paramDict['droppedPacketsLimit'])
                            resultStatus = 'FAIL'
                        # Evaluate VQA Impared Frame Count #
                        imparedFrameCount = int(row['QmVideo Impaired B-Frames']) + int(row['QmVideo Impaired I-Frames']) + int(row['QmVideo Impaired P-Frames'])
                        if int(imparedFrameCount) <= int(paramDict['imparedFramesLimit']):
                            print 'PASS :: ' + '<' + row['Entity Name'] + '> ' + 'Impared frame count ' + str(imparedFrameCount) + ' was less than or equal to ' +  str(paramDict['imparedFramesLimit'])
                        else:
                            print 'FAIL :: ' + '<' + row['Entity Name'] + '> ' + 'Impared frame count ' + str(imparedFrameCount) + ' was greater than ' +  str(paramDict['imparedFramesLimit'])
                            resultStatus = 'FAIL'
                    # Evaluate Zap Statistics #
                    if re.match('.*' + paramDict['zapAppType'] + '.*', row['Entity Name'], re.IGNORECASE):
                        # Evaluate Mean Join Time #
                        if float(row['Mean Join Time ms']) <= float(paramDict['joinTimeAvgLimit']):
                            print 'PASS :: ' + '<' + row['Entity Name'] + '> ' + 'JoinTimeAvg ' + str(row['Mean Join Time ms']) + ' was less than or equal to ' +  str(paramDict['joinTimeAvgLimit'])
                        else:
                            print 'FAIL :: ' + '<' + row['Entity Name'] + '> ' + 'JoinTimeAvg ' + str(row['Mean Join Time ms']) + ' was greater than ' +  str(paramDict['joinTimeAvgLimit'])
                            resultStatus = 'FAIL'
                        # Evaluate Zap Dropped Packets #
                        if int(row['Dropped Packets']) <= int(paramDict['droppedPacketsLimit']):
                            print 'PASS :: ' + '<' + row['Entity Name'] + '> ' + 'Total packet loss ' + str(row['Dropped Packets']) + ' was less than or equal to ' +  str(paramDict['droppedPacketsLimit'])
                        else:
                            print 'FAIL :: ' + '<' + row['Entity Name'] + '> ' + 'Total packet loss ' + str(row['Dropped Packets']) + ' was greater than ' +  str(paramDict['droppedPacketsLimit'])
                            resultStatus = 'FAIL'
                        # Evaluate Missed Joins #
                        exptJoins = float(row['Joins Completed']) / float(row['Joins Initiated'])
                        if float(exptJoins) >= float(paramDict['joinPercLimit']):
                            print 'PASS :: ' + '<' + row['Entity Name'] + '> ' + 'Percentage Joins completed ' + str(exptJoins * 100) + ' was greater than or equal to ' +  str(paramDict['joinPercLimit'] * 100)
                        else:
                            print 'FAIL :: ' + '<' + row['Entity Name'] + '> ' + 'Percentage Joins completed ' + str(exptJoins * 100) + ' was less than ' +  str(paramDict['joinPercLimit'] * 100)
                            resultStatus = 'FAIL'
                        # Evaluate Missed Leaves #
                        exptLeaves = float(row['Leaves Completed']) / float(row['Leaves Initiated'])
                        if float(exptLeaves) >= float(paramDict['leavePerLimit']):
                            print 'PASS :: ' + '<' + row['Entity Name'] + '> ' + 'Percentage Leaves completed ' + str(exptLeaves * 100) + ' was greater than or equal to ' +  str(paramDict['leavePerLimit'] * 100)
                        else:
                            print 'FAIL :: ' + '<' + row['Entity Name'] + '> ' + 'Percentage Leavs completed ' + str(exptLeaves * 100) + ' was less than ' +  str(paramDict['leavePerLimit'] * 100)
                            resultStatus = 'FAIL'
                        # Evaluate Joins vs Leaves #
                        exptZap = float(row['Leaves Completed']) / float(row['Joins Completed'])
                        if float(exptZap) >= float(paramDict['zapPerLimit']):
                            print 'PASS :: ' + '<' + row['Entity Name'] + '> ' + 'Percentage Leaves completed against joins ' + str(exptZap * 100) + ' was greater than or equal to ' +  str(paramDict['zapPerLimit'] * 100)
                        else:
                            print 'FAIL :: ' + '<' + row['Entity Name'] + '> ' + 'Percentage Leaves completed against joins ' + str(exptZap * 100) + ' was less than ' +  str(paramDict['zapPerLimit'] * 100)
                            resultStatus = 'FAIL'

                else:
                    print('%s :: Set to Out of Service or no DHCP attained, skip analysis' % row['Entity Name'])

        if resultStatus == 'PASS':
            print "**********All IGMP measures are within limits**********"
        else:
            print "##########All IGMP measures are not within limits########"

    def evaluateHttpApplications(self, paramDict):
        """
        This method read Summary_Http_Client.csv file and evaluate all HTTP applications.

        *Parameters* :
        - paramDict : <Dictionary> ; dictionary contains key, value pair . possible values are
        | *Key* | *Value* | *Comment* |
        | *csvFilePath* | <string> | Path to Summary_Multicast_Client.csv file. Ex: C:\\diversifEyeClient\\IPTV\\output\\Miscellaneous\\Summary_HTTP_Client.csv
        | *appType* | <string> | Type of application to evaluate, this procedure will evaluate only HTTP applications.. Ex: HTTP |
        | *goodput* | <float> | Shaped rate in kpbs |
        | minGoodput | <float> | MinGoodput. Default value is 0.85 |

        *Returns* : None
        """
#------>if type(paramDict) is not dict:
        if not paramDict:
            raise AssertionError('paramDict is not dictionary')
        elif not paramDict:
            raise AssertionError('paramDict is empty')

        manDateParams = ['csvFilePath', 'appType', 'goodput']
        for param in manDateParams:
            if param not in paramDict.keys():
                raise AssertionError('evaluateHttpApplications: %s is not provided in argument list which is manadatory arguement' % param)

        if not paramDict.has_key('minGoodput') or paramDict['minGoodput'] == '':
            paramDict['minGoodput'] = 0.85

        resultStatus = "PASS"

        minGoodput = float(float(paramDict['goodput']) * float(paramDict['minGoodput']))

        with open(paramDict['csvFilePath']) as csvfile:
            for row in csv.DictReader(csvfile):
                ipAddress = str(row['IP Address']).split('/', 1)[0]
                if ipAddress != '0.0.0.0':
                    # Evaluate HTTP Statistics #
                    if re.match('.*' + paramDict['appType'] + '.*', row['Entity Name'], re.IGNORECASE):
                        # Evaluate Goodput #
                        if float(row['Mean In KiloBits/s']) >= float(minGoodput):
                            print 'PASS :: ' + '<' + row['Entity Name'] + '> ' + 'Goodput value ' + str(row['Mean In KiloBits/s']) + ' was greater than or equal to ' +  str(minGoodput)
                        else:
                            print 'FAIL :: ' + '<' + row['Entity Name'] + '> ' + 'Goodput value ' + str(row['Mean In KiloBits/s']) + ' was less than ' +  str(minGoodput)
                            resultStatus = 'FAIL'
                else:
                    print('%s :: Set to Out of Service or no DHCP attained, skip analysis' % row['Entity Name'])

        if resultStatus == 'PASS':
            print "********** All HTTP measures are within limits **********"
        else:
            print "########## All HTTP measures are not within limits ########"


if __name__ == '__main__':
    instance = TrafficAnalysis()
    instance.evaluateHttpApplications()