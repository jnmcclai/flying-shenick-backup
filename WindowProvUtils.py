from collections import OrderedDict
from ftplib import FTP
from robot.libraries.BuiltIn import BuiltIn
from robot.libraries.Telnet  import Telnet
from robot.api import logger
import csv
import datetime
import os
import os.path
import platform
import re
import robot
import string
import subprocess as s
import sys
import time
import time, datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom


class WindowProvUtils:
    """
    Lib For Windows Related Function  .
    """

    ROBOT_LIBRARY_VERSION = '0.1'
    ROBOT_LIBRARY_SCOPE   = 'GLOBAL'
    global_init           = 0
    global_timeout        = 120
    min_robot_version     = 20801

    def __init__(self):

        self._get_robot_version()

    def _get_robot_version(self):
        version = robot.get_version().split('.')

    def _HostOs(self):
        """
        This procedure uses the platform.system() call to determine the operating system of the host.
        Certain functions can be called based on which OS is in use.
        """
        hostOs = platform.system()
        if hostOs != 'Windows' and hostOs != 'Linux':
            raise AssertionError('Current operating system not compatiable. Have some sense... Use Windows or Linux!')
        print 'Current operating system is ' + hostOs
        return hostOs

    def changeShenickPhyIntfInXML(self,sourceXmlFile,oldPhyIntf, newPhyIntf):
         """
         Descriptions:
         sourceXmlFile : XML file name with PATH
         """
         Test_file = open(sourceXmlFile,'r')
         xmldoc = minidom.parse(Test_file)
         x = xmldoc.getElementsByTagName("physical_interface")
         for i in range(len(x)):
            y = x[i].childNodes[0].nodeValue
            if y == oldPhyIntf :
                print ('ok')
                x[i].childNodes[0].replaceWholeText(newPhyIntf)
                print(x[i].childNodes[0].nodeValue)
                open(sourceXmlFile,'w').write(xmldoc.toxml())
         Test_file.close()

    def copyFile(self, outputPath, shenickExeDir):
        """

        :param outputPath:
        :param shenickExeDir:
        :return:
        """
        retVal = os.system('xcopy /E /Y %s %s' %(outputPath, shenickExeDir ))
        if int(retVal) == 0:
          print("Windows: Server and Client Summary files copied successfully")
        else:
          raise AssertionError("Windows: Server and Client Summary files not copied successfully")
        return True

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
        #if type(paramDict) is not dict:
        if not paramDict:
            raise AssertionError('paramDict is not dictionary')
        elif not paramDict:
            raise AssertionError('paramDict is empty')

        manDateParams = ['serverIp', 'userName', 'password', 'sourceFilePath', 'destFilePath']
        for param in manDateParams:
            if param not in paramDict.keys():
                raise AssertionError('copyFileFromServer: %s is not provided in argument list which is manadatory arguement' % param)

        sourcePath = []
        length = len(paramDict['sourceFilePath'].split('/'))
        sourceFileName = paramDict['sourceFilePath'].split('/')[length - 1]
        for i in range(0, length - 1):
            sourcePath.append(paramDict['sourceFilePath'].split('/')[i])
        separator = '/'
        sourcePath = separator.join(sourcePath)

        destPath = []
        length = len(paramDict['destFilePath'].split('/'))
        destFileName = paramDict['destFilePath'].split('/')[length - 1]
        for i in range(0, length - 1):
            destPath.append(paramDict['destFilePath'].split('/')[i])
        separator = '/'
        destPath = separator.join(destPath)

        copyStatus = 'FAIL'
        getStatus = 'FAIL'

        ftp = FTP('%s' % paramDict['serverIp'])
        ftp.login(paramDict['userName'], paramDict['password'])
        ftp.cwd('%s' % sourcePath)
        filenames = ftp.nlst() # get filenames within the directory
        for filename in filenames:
          if filename == sourceFileName:
              file = open(paramDict['destFilePath'], 'wb')
              ftp.retrbinary('RETR '+ destFileName, file.write)
              file.close()
              getStatus = 'PASS'
        if getStatus == 'FAIL':
            raise AssertionError('File %s is not available in the dir %s' % (sourceFileName, sourcePath) )

        files = os.listdir(destPath)
        for filename in files:
          if filename == destFileName:
              print('File %s has been copied successfully to dir %s' % (filename, destPath) )
              copyStatus = 'PASS'

        if copyStatus == 'FAIL':
              raise AssertionError('File %s has not been copied successfully to dir %s' % (destFileName, destPath) )

    def copyShenickXmlFileToLocal(self, sourceXmlPath, xmlFileName):
        """
        Descriptions:Copy Shenick XML file from perfoce to local pc in dir C:\\Shenick\\
        """
        sourceXmlFile = '%s%s.xml' % (sourceXmlPath , xmlFileName)
        os.system('copy %s C:\\ShenickExeDir\\' % sourceXmlFile)
        trafficXmlFile = 'C:\\ShenickExeDir\\%s.xml' % xmlFileName
        # os.chmod( trafficXmlFile,stat.S_IWRITE)
        return trafficXmlFile

    def delFile(self, analysisDir, fileName):
        """
        :param analysisDir:
        :param fileName:
        :return:
        """
        os.chdir(analysisDir)
        files = os.listdir(analysisDir)
        for filename in files:
          if filename == fileName:
              print(fileName)
              os.remove(fileName)
        return True

    def runAnalysisBatchFile(self, resultsFilePath, outputPath):
        """
        This method runs Analyse.bat on give results (*.zip) and saves the summary csv files in given output path.

        *Parameters* :
        - *resultsFilePath*  : <string> ; Path to results zip file, ex: C:\\diversifEyeClient\\analysis\\bin\\IPTV.Zip
        - *outputPath*      : <string> ; Path to save the output summary results files. ex: C:\\diversifEyeClient

        *Returns* : None
        """
        resultsPath = []
        length = len(resultsFilePath.split('\\'))
        zipFileName = resultsFilePath.split('\\')[length - 1]
        for i in range(0, length - 1):
            resultsPath.append(resultsFilePath.split('\\')[i])
        separator = '\\'
        resultsPath = separator.join(resultsPath)

        os.chdir(resultsPath)
        status = os.system('Analyse.bat %s --script ADTRAN.R --viewer none --output png --to %s' % (zipFileName, outputPath))
        ### Here os.system command always returns status code 0, i think we need to use subprocess instead of os module to get the output and check the Error message in the output ###
        if int(status) == 0:
            print("Analysis.bat ran successfully")
        else:
            raise AssertionError("Analisys.bat has not been executed successfully")

    def shenickXmlSamplingIntervalChange(self, sourceXmlFile, samplingInterval):
        """
        This procedure will modify an existing Shenick (XML) file using the desired Sampling Interval.

        *Parameters* :
        - paramDict : <Dictionary> ; dictionary contains key, value type. discription
        | *Key* | *Value type* | *Comment* |
        | *sourceXmlFile* | <string> | XML file name (with file path) of script which will be modified |
        | *samplingInterval* | <string> | Desired sampling interval. Please use 30sec, 1min, or 5min |

        *Returns* : None
        """
        # Set a sampling interval that is compatible to Shenick XML formatting
        if str(samplingInterval) == '30sec':
            sampleInterval = 'Thirty Seconds'
        elif str(samplingInterval) == '1min':
            sampleInterval = 'One Minute'
        elif str(samplingInterval) == '5min':
            sampleInterval = 'Five Minutes'
        else:
            raise AssertionError('Invalid sampling interval entered. Please use 30sec, 1min, or 5min.')
        # Set up source file for parsing and modification
        xmlFile = sourceXmlFile + '.xml'
        # Search through XML file for desired element and replace value with given sampling interval
        tree = ET.parse(xmlFile)
        for elem in tree.findall('.//tce_normal_stats_sample_interval'):
            elem.text = sampleInterval
        # Write XML 'tree' to new XML file and inform user of success status
        try:
            tree.write(xmlFile)
            logger.info('XML file was successfully modified and rewritten', False, True)
        except:
            raise AssertionError('XML file was not successfully modified and rewritten')

if __name__ == '__main__':
    #create an instance
    instance = WindowProvUtils()
    # Execute function
    instance.shenickXmlSamplingIntervalChange('C:/ShenickExeDir/test_script', '1min')