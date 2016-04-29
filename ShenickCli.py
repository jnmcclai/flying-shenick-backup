#!/usr/bin/python
# coding: utf-8

import os
import re
import time
import tempfile
import paramiko
import scp
import csv
from robot.api import logger

class ShenickCli():
    """
    Library for SSH communication with the Shenick and defines procedures for CLI commands

    *Parameters* :
     | *Parameter* | *Type* | *Description* |
     |*tvmcIp* | <string> | IpAddress of TVM-C |
     |*tgName* | <string> | Shenick test group path and name in the format //Folder/testName |
     | tvmUser | <string> | User name, default value <adtran> |
     | partition | <integer> | Partition number, default value <1> |
     | chassisType | <string>  | Chassis type, default value <5500> |

    *Returns* : None

    Requirements:
    - paramiko
    - pycrypto
    - ecdsa
    - scp
    """

    ROBOT_LIBRARY_VERSION = '0.1'
    ROBOT_LIBRARY_SCOPE   = 'GLOBAL'

    def __init__(self, tvmcIp, tgName, tvmUser= 'adtran', partition=1, chassisType='5500'):
        self._tvmcIp    = tvmcIp
        self._tvmcUser  = tvmUser
        self._partition = partition
        self._sshUser   = 'cli'
        self._sshPwd    = 'diversifEye'
        self._tmpFile   = None
        self._sshClient = None
        self._sshChannel = None
        self._tgName    = tgName
        self._chassisType = chassisType
        """
        The last option was added for backwards compatibility with the DiversifEye 8400 and 5500
        Chassis type can also be used to detect TVM 2, 3 and 5 (Cores/port)
        """

        self._execSshCommand('cli configure cliDefaultDiversifEyeUser=%s' % self._tvmcUser)
        self._execSshCommand('cli configure cliDefaultPartition=%s' % self._partition)

    def __del__(self):
        if self._tmpFile is not None:
            os.close (self._tmpFile[0])
            os.remove(self._tmpFile[1])

    def _write(self, string):
        """
        Write string to testGroup

        *Parameters*    :
        - string        : <string> ; String to be write into test group

        *Returns* : None

        """
        if self._tmpFile is None:
            raise AssertionError('no test group created, please use testGroupCreate first')

        with open(self._tmpFile[1], 'a') as perlFile:
            perlFile.write(string + os.linesep + os.linesep)

    def _createSshClient(self):
        """
        Creates a ssh client, invokes a shell and returns a channel to this shell.

        *Parameters* : All values provided from __init__

        *Returns* : None
        """
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(self._tvmcIp, port=22, username=self._sshUser, password=self._sshPwd, allow_agent=False )
            channel = client.invoke_shell(width=256)
            self._sshClient = client
            self._sshChannel = channel
        except:
            raise AssertionError('Could not open SSH connection.')
        return client, channel

    def _reconnectSshClient(self):
        """
        Checks if a ssh client is already open and, if so, checks if it is still active.
        Otherwise a new client is started. Returns the current ssh client.

        *Parameters* : All values provided from __init__

        *Returns* : None

        """
        try:
            #  check for active SSH session
            if self._sshClient.get_transport().is_active() is True:
                pass
        except:
            """
            If a session hasn't been opened or dropped during testing, this
            sequence will call create SSH Client [session],
            then enable default options and lastly, set the default user & partition.

            The last call will associate all subsequent CLI commands to the defined
            user and partition.  The -u and -p values need not, then be passed.

            Partition is defaulted to 1 but may be 1-6 on a DiversifEye chassis.
            """
            self._sshClient, self._sshChannel = self._createSshClient()
            self._enableDefaultCliOptions()
            self._setCliDefaultUserPartition()
        finally:
            return self._sshClient, self._sshChannel

    def _scpPutFile(self, local, remote):
        """
        Put file to shenick controller.

        *Parameters*    :
        - *local*         : <string>  ; Path for local file
        - *remote*        : <string>  ; Path to remote location

        *Returns* : None
        """
        client, channel = self._reconnectSshClient()
        try:
            scpClient = scp.SCPClient(client.get_transport())
            scpClient.put(local, remote)
        except:
            raise AssertionError('scp put failed.')

    def _scpGetFile(self, remote, local):
        """
        Get file from shenick controller.

        *Parameters*    :
        - *remote*        : <string>  ; Path for remote file
        - *local*         : <string>  ; Path to local location

        *Returns* : None
        """
        client, channel = self._reconnectSshClient()
        try:
            scpClient = scp.SCPClient(client.get_transport())
            scpClient.get(remote, local)
        except:
            raise AssertionError('scp get failed.')

    def _execSshCommand(self, command):
        """
        Execute the CLI command on shenick.

        *Parameters*    :
        - *command*     : <string>  ; Command to be executed

        *Returns* : None
        """
        client, channel = self._reconnectSshClient()
        output = ''
        try:
            # clear leftovers
            while channel.recv_ready():
                channel.recv(1)
            # send the command
            channel.send(command + '\n')
            # wait until channel has data
            while not channel.recv_ready():
                time.sleep(0.1)
            # read until end of prompt
            while not output.endswith('$ '):
                while channel.recv_ready():
                    output += channel.recv(1)
            # check for errors
            if 'cli>ERROR:' in output:
                assert False, output

        except AssertionError as e:
            raise AssertionError('ssh command "%s" failed with error "%s"' % (command, e))

        # return output without command and prompt
        return '\n'.join(output.splitlines()[1:-1])

    def _enableDefaultCliOptions(self):
        """
        Enables persistent background mode if it is not enabled yet. Suggested by shenick documentation.
        Also, disable notifications, might conflict with output of other commands.

        *Parameters*  : None

        *Returns* : None

        """
        if not 'true' in self._execSshCommand('cli available'):
            self._execSshCommand('cli start')

    def _setCliDefaultUserPartition(self):
        """
        This procedure will set the default user and partition.  This is a DiversifEye command where there can
        be multiple used accessing the same shelf.  This defined all commands on the CLI session are identified
        to a a specific user and partition .All variables needed from this command are inherited from the __init__ function.

        *Parameters*  : None

        *Returns*: None
        """
        self._execSshCommand('cli configure cliDefaultDiversifEyeUser=%s' % self._tvmcUser)
        self._execSshCommand('cli configure cliDefaultPartition=%s' % self._partition)

    def getListApplications(self):
        """
        This procedure will get the list of applications for a given testGroup.

        *Parameters*    :  None, Test Group is a defined as a global parameter

        *Returns*       : This procedure returns the list of applications as a string
        """
        output =  self._execSshCommand('cli listApplications %s' % self._tgName)

        tempList = []
        for line in output.splitlines():
            line = line.strip()

            if re.match('^IP', line):
                line = line.split(' ')[0]
                tempList.append(line.split('/')[1])

        return tempList

    def getHeadEndMosStatistic(self, channelPool=[213, 219, 207, 215, 211, 214, 204, 202, 218, 18, 216, 20, 16, 210, 212, 200], headEndIp='10.13.254.32', headEndPort=22, headEndUser='cli', headEndPwd='diversifEye', tg=''):
        """
        This procedure navigates to the Video Head End Server and gets the minimum MOS.
        The min MOS is used during TrafficAnalysis calls to score the actual application results where:

        Head End - Actual = Degradation due to system (jitter, loss, etc.) = should be 0

        *Parameters*        :
        - *channelPool*     :  <list>  ; A channel pool list - HD or STD (e.g. HD: 213 219 207 215 211 214 204 202 218 18 216 20 16 210 212 200| STD: 4 8 24 31 33 40 91)
        - *headEndUser*     :  <string> ; Head end default user
        - *headEndPwd*      :  <string> ; Head end default pwd
        - *tg*              :  <string> ; Head end test group (Default to '')

        *Returns*           :  Returns max and min MOS from head end in form of a dictionary with minMos and maxMos keys
        """

        #initialize some variables
        headEndMosList = list()
        mosDict = dict()
        mosMin = 0
        mosMax = 5
        user = 'hjohnson'
        partition = 2

        #create a new instance of the class to make use of the ssh methods
        try:
            headEndInstance = ShenickCli(headEndIp, tg)

            #connect SSH session to head end
            headEndInstance._createSshClient()

            #set the partition - ideally use the class method but hardcoded for now
            headEndInstance._execSshCommand('cli configure cliDefaultDiversifEyeUser=%s' % user)
            headEndInstance._execSshCommand('cli configure cliDefaultPartition=%s' % partition)

            #loop over channel pool and get latest MOS
            for channel in channelPool:
                appName = str(channel) + "-Headend"
                mos = headEndInstance._execSshCommand('cli getStat "{0}" "QmVideo MOS" Normal Application'.format(appName))
                headEndMosList.append(mos)
            
            #print out MOS list for sanity
            #print headEndMosList

            #get min and max MOS
            mosMin = min(headEndMosList)
            mosMax = max(headEndMosList)
            print mosMin
            print mosMax

            #logging
            # logger.info("Min MOS: {0}".format(mosMin), False, True)
            # logger.info("Max MOS: {0}".format(mosMax), False, True)
            #logger.warn("Min MOS: {0}".format(mosMin))
            #logger.console("\nMin MOS: {0}".format(mosMin))
        
            #return 
            mosDict = {'mosMin': mosMin, 'mosMax': mosMax}
            #returning just min MOS for robot purposes
            return mosMin
            #return mosDict

        except:
            raise AssertionError('not able to retrieve head end MOS stats')

    def enableDisableApplications(self, applications, status='Enabled'):
        """
        Enable/disable all or a list of applicaionts (hosts)

        *Parameters*             :
        - *applications*         :  'All' or a list of applications to enable/disable
        - *status*               : <string> Enabled|Disabled
        """

        if type(applications) is not list:
            #enable/disable all
            self._execSshCommand("cli setAdminStateOfApplicationsInTestGroup {0} '{1}'".format(self._tgName, status))
        else:
            #get list of applications
            #applicationList = self.getListApplications()
            #enable/disable a list of applications
            self._execSshCommand("cli setAdminStateOfApplications {0}/IP/{1} '{2}'".format(self._tgName, ',{0}/IP/'.format(self._tgName).join(applications), status))

    def inServiceOutServiceApplications(self, applications, status='In Service'):
        """
        IS/OOS all or a list of applicaionts (hosts)

        *Parameters*             :
        - *applications*         :  'All' or a list of applications to enable/disable
        - *status*               : <string> In Service|Out of Service
        """
        #get list of applications
        applicationList = self.getListApplications()

        if type(applications) is not list:
            #enable/disable all
            self._execSshCommand("cli setServiceStateOfApplicationsInTestGroup {0} '{1}'".format(self._tgName, status))
        else:
            #get list of applications
            #applicationList = self.getListApplications()
            #enable/disable a list of applications
            self._execSshCommand("cli setServiceStateOfApplications {0}/IP/{1} '{2}'".format(self._tgName, ','.join(applications), status))


    def getShenickCliStatistic(self, appName, stat, statType='Application', normal='Normal'):
        """
        This procedure will get the list of applications for a given testGroup.

        *Parameters*        :
        - *appName*         : <string> Name of application or host to get statistics for. Only name is needed not the whole path
        - *stat*            : <string> Name of the statistic (corresponding to the column in the appName table)
        - *statType*        : <string> Type of appName (Application or Host).
        - *normal*          : <string> Statistical collection method.  Default value = Normal, alternately = Fine.

        *Returns*           : stats
        """
        #get the stat
        cmd = 'cli getStat {0} "{1}" {2} {3}'.format(appName, stat, normal, statType)
        output = self._execSshCommand(cmd)

        #return the output
        return output

    def startTestGroup(self):
        """
        This procedure will execute the cli command to start the testGroup.

        *Parameters*    :  None, Test Group is a defined as a global parameter

        *Returns*       : None
        """
        self._execSshCommand('cli startTestGroup "%s"' % self._tgName)


    def stopTestGroup(self):
        """
        This procedure will execute the cli command to stop the testGroup.

        *Parameters*    :  None, this call will stop any currently running tests

        *Returns*       : None
        """
        try:
            self._execSshCommand('cli stopTestGroup')
            logger.info("Test group stopped")
        except:
            logger.info('No test group running...')

        return 'pass'

    def testGroupImport(self, sourceFile):
        """
            Import (upload) test case from host to Shenick

            *Parameters*    :
            | sourceFile | <string> | The location and file on the host machine, i.e. PC |

            Note:  The test group in the format of //Folder/testCase is defined and passed as a system
              parameter during the init phase.

              If using a pre-existing test group, this procedure call is not needed.

            *Returns* : None
        """

        try:
            self._execSshCommand('cli importTestGroup "%s %s"' % (self._tgName, sourceFile))
            logger.info('Test group imported to Shenick...')
        except:
            logger.error('Test group could not be found on host machine...')

    def testGroupDelete(self,):
        """
        Deletes a test group on the controller.

        *Parameters*    :  None, Test Group is a defined as a global parameter

        *Returns*       : None
         """
        try:
            self._execSshCommand('cli deleteTestGroup "%s"' % ( self._tgName))
            logger.info('Test group deleted from Shenick...')
        except:
            self.stopTestGroup()
            self._execSshCommand('cli deleteTestGroup "%s"' % (self._tgName))
            logger.info('Test group stopped and deleted from Shenick...')

        return True

    def saveStats(self, paramDict):
        """
        This method saves results as zip file in shenick controller.

        *Parameters* :
        - paramDict : <Dictionary> ; dictionary contains key, value pair . possible values are
        | *Key* | *Value* | *Comment* |
        | *fileName* | <string> | The file name to be applied to the stats.  While the file is automatically saved in .zip format you must include .zip in the file name.
        | statsType | <string> | A Java-style regular expression matching available statistics types. Valid values <Fine || Normal> |
        | entityType | <string> | The entity type. Valid values <Aggregate || Host || Application || Interface> |
        | columns | <string> | Comma-separated list of column labels specifying the columns to save and how they are to be presented. Ex: 'Time,In Service,In Bits/s,In Packets/s,Out Bits/s,QmVideo MOS' |

        *Returns* : None
        """
#------> if type(paramDict) is not dict:
        #returns non dict so forcing this
        if not paramDict:
            raise AssertionError('paramDict is not dictionary')
        elif not paramDict:
            raise AssertionError('paramDict is empty')

        if not paramDict.has_key('fileName') or paramDict['fileName'] == '':
            raise AssertionError('saveStats: fileName is not provided in argument list which is manadatory arguement')

        if not paramDict.has_key('statsType') or paramDict['statsType'] == '':
            paramDict['statsType'] = 'Normal'

        if not paramDict.has_key('entityType') or paramDict['entityType'] == '':
            paramDict['entityType'] = 'Application'

        if not paramDict.has_key('columns'):
            paramDict['columns'] = ''

        self._execSshCommand('cli saveStats %s Columns=%s StatsType=%s EntityType=%s' % (paramDict['fileName'], paramDict['columns'], paramDict['statsType'], paramDict['entityType']))

if __name__ == '__main__':

    #create an instance
    instance = ShenickCli("10.13.225.18", "//GPON/GPON_Triple_Play_LoadTest", "IPTV", 2)
    
    #grab the head end MOS stuff
    #instance.getHeadEndMosStatistic()

    #getShenickCliStatistic
    # print instance._execSshCommand("cli listApplications")
    # print instance.getShenickCliStatistic('TA362-video1', 'QmVideo MOS') 
    
    listOfApplications = ['Client_HTTP_ONT16', 'Client_HTTP_ONT15', 'Client_HTTP_ONT14']

    instance.inServiceOutServiceApplications(listOfApplications, "Out of Service")
    time.sleep(3)
    instance.inServiceOutServiceApplications(listOfApplications, "In Service")
    time.sleep(3)
    instance.enableDisableApplications(listOfApplications, "Disabled")
    time.sleep(3)
    instance.enableDisableApplications(listOfApplications, "Enabled")
    time.sleep(3)
    instance.enableDisableApplications('all', "Disabled")
    time.sleep(3)
    instance.enableDisableApplications('all', "Enabled")
    time.sleep(3)
    instance.inServiceOutServiceApplications('all', "Out of Service")
    time.sleep(3)
    instance.inServiceOutServiceApplications('all', "In Service")