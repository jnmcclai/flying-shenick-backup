#!/usr/bin/python

import os
import re
import scp
import csv
import glob
import shutil
import zipfile
import tempfile
import paramiko

class Shenick():
  """
  Mandatory parameter:
  - tvmcIp: ipAddress of TVM-C

  Optional parameter:
  - tvmUser, default: robot

  Usage:
  - creates test group 'robot' as user 'robot' (or the username specified) -> open gui as this user to see what happens!
  - see examples file

  Requirements:
  - paramiko (gentoo: "emerge paramiko")
  - scp (gentoo: "pip install scp")
  """

  def __init__(self, tvmcIp, tvmUser='robot'):
    self._tvmcIp    = tvmcIp
    self._tvmcUser  = tvmUser
    self._tgName    = 'robot'
    self._sshUser   = 'cli'
    self._sshPwd    = 'diversifEye'
    self._tmpFile   = None
    self._sshClient = None

  def __del__(self):
    if self._tmpFile is not None:
      os.close (self._tmpFile[0])
      os.remove(self._tmpFile[1])

  def _write(self, string):
    if self._tmpFile is None:
      self._initPerlScript()

    with open(self._tmpFile[1], 'a') as perlFile:
      perlFile.write(string + os.linesep)

  def _initPerlScript(self, lowMemory='0'):

    if self._tmpFile is None:
      self._tmpFile = tempfile.mkstemp(prefix='shenick_')
    else:
      os.close (self._tmpFile[0])
      os.remove(self._tmpFile[1])
      self._tmpFile = None

    # imports
    self._write('use strict;')
    self._write('use warnings FATAL=>qw(all);')
    self._write('use diversifEye::TestGroup;')
    self._write('use diversifEye::Misc;')
    self._write('use diversifEye::PingApp;')
    self._write('use diversifEye::DirectVirtualHost;')
    self._write('use diversifEye::Dhcp4Server;')
    self._write('use diversifEye::Dhcp4Config;')
    self._write('use diversifEye::Dhcp4Options;')
    self._write('use diversifEye::RemoteId;')
    self._write('use diversifEye::IpAddress;')
    self._write('use diversifEye::PppoeServer;')
    self._write('use diversifEye::PppoeSettings;')
    self._write('use diversifEye::TeraFlowServer;')
    self._write('use diversifEye::TeraFlowClient;')
    self._write('use diversifEye::FtpResource;')
    self._write('use diversifEye::FtpResourceList;')
    self._write('use diversifEye::FtpCommand;')
    self._write('use diversifEye::FtpCommandList;')
    self._write('use diversifEye::FtpClient;')
    self._write('use diversifEye::FtpServer;')
    self._write('use diversifEye::PsAlnum;')
    self._write('use diversifEye::PsIpa;')
    self._write('use diversifEye::PsMac;')
    self._write('use diversifEye::PsMacFromIf;')
    self._write('use diversifEye::PsIfl;')
    self._write('use diversifEye::PsVlanId;')
    self._write('use diversifEye::PsHost;')

    # create a test group; define name here as we need the same name to delete old test groups
    self._write('my $Tg = diversifEye::TestGroup->new(name=>"%s", LowMemory=>%s);' % (self._tgName, lowMemory) )

  def _createSshClient(self):
    try:
      client = paramiko.SSHClient()
      client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      client.connect(self._tvmcIp, username=self._sshUser, password=self._sshPwd )
    except:
      raise AssertionError('could not open ssh connection.')
    return client

  def _reconnectSshClient(self):
    """
    Checks if a ssh client is already open and, if so, checks if it is still active.
    Otherwise a new client is started. Returns the current ssh client.
    """
    try:
      if self._sshClient.get_transport().is_active() is True:
        pass
    except:
      self._sshClient = self._createSshClient()
      self._enableDefaultCliOptions()
    finally:
      return self._sshClient

  def _scpPutFile(self, local, remote):
    client = self._reconnectSshClient()
    try:
      scpClient = scp.SCPClient(client.get_transport())
      scpClient.put(local, remote)
    except:
      raise AssertionError('scp put failed.')

  def _scpGetFile(self, remote, local):
    client = self._reconnectSshClient()
    try:
      scpClient = scp.SCPClient(client.get_transport())
      scpClient.get(remote, local)
    except:
      raise AssertionError('scp get failed.')

  def _execSshCommand(self, *commands):
    client = self._reconnectSshClient()
    try:
      for command in commands:
        stdin, stdout, stderr = client.exec_command(command)
        # this will block until command has finished, we need this!
        # also, we need the return code to check if the command was successful
        returnCode = stdout.channel.recv_exit_status()
        if returnCode != 0:
          assert False, stderr.read()
    except AssertionError as e:
      raise AssertionError('ssh command "%s" failed with error "%s"' % (command, e))

    return stdout.read()

  def _enableDefaultCliOptions(self):
    """
    Enables persistent beckground mode if it is not enabled yet. Suggested by Shenick documentation.
    Also, disable notifications, might conflict with output of other commands.
    """
    if not 'true' in self._execSshCommand('cli available'):
      self._execSshCommand('cli start')

    # found in CLI_User_Guide.pdf but cli does not know this...
    #self._execSshCommand('cli reportNotifications false')

  def initializeTestGroup(self, useLowMemoryMode='false'):
    """
    Creates a new test group, discarding all configuration done before. No changes at TVM-C are made.

    - useLowMemoryMode: If true, RAM use by perl is much reduced, but there are some restrictions on
      the order in which certain elements may be added. If false (the default), the restrictions are
      removed, but RAM use can be excessive for large test cases.
    """
    lowMemoryDict = {
      'false':  '0',
      'true':   '1'
    }

    #self._tmpFile.close()
    #self._tmpFile = tempfile.NamedTemporaryFile()
    self._initPerlScript(lowMemoryDict[useLowMemoryMode.lower()])

  def uploadTestGroup(self):
    """
    Uploads the current configuration to the tvm controller.
    """
    self._write('$Tg->End();')
    # copy perl to tvm-c
    self._scpPutFile(self._tmpFile[1], '/tmp/robot.pl')
    # execute remote perl
    self._execSshCommand('perl /tmp/robot.pl > /tmp/robot.xml')
    # try to stop a still running test group
    try:
      self._execSshCommand('cli -u %s stopTestGroup "//%s"' % (self._tvmcUser, self._tgName))
    except:
      pass
    # try to delete a already existing test group
    try:
      self._execSshCommand('cli -u %s deleteTestGroup "//%s"' % (self._tvmcUser, self._tgName))
    except:
      pass

    # load test group
    self._execSshCommand('cli -u %s importTestGroup "//" /tmp/robot.xml' % self._tvmcUser)

    # start over
    self.initializeTestGroup()

  ### tvm-c cli stuff

  def downloadCvsFile(self, localPath):
    """
    Creates a zip file containing cvs result files on the TVM-C and downloads it to the local pc. This keyword
    ist not required for _getStatisticsFromZipFile_ (it will get its own copy)
    - localPath: string, path where the zip file should be saved. Default file name is "csvStatistics.zip"
      if no file name in localPath is given.

    | downloadCvsFile | /home/sff00009 | Comment | creates /home/sff00009/csvStatistics.zip |
    | downloadCvsFile | /home/sff00009/ | Comment | creates /home/sff00009/csvStatistics.zip |
    | downloadCvsFile | /home/sff00009/myCvsFile.zip | Comment | creates /home/sff00009/myCvsFile.zip |
    """
    remotePath = '/tmp/csvStatistics.zip'

    self._execSshCommand('cli -u %s saveStats %s' % (self._tvmcUser, remotePath) )
    self._scpGetFile(remotePath, localPath)
    self._execSshCommand('rm %s' % remotePath)

  def getStatisticsFromZipFile(self, returnType='cumulative'):
    """
    TODO: As default, only the cumulative values are returned because otherwise it's A LOT of data,
          especially if it's a long running test. Fine statistics don't seem to be included...

          What to do if entity is "Out of service"? Right now it will always be used in calculations.
          Might be a problem for "rate" stats?
    """
    stats   = {}
    tempDir = tempfile.mkdtemp()

    try:
      # save stats on tvm-c and copy them to local machine
      self.downloadCvsFile(tempDir)
      # extract zip file
      zip = zipfile.ZipFile(os.path.join(tempDir, 'csvStatistics.zip'))
      zip.extractall(tempDir)

      for entityType in ['Aggregate', 'Host', 'Interface', 'TestGroup']: # maybe add 'Meta', not sure if useful

        stats[entityType.lower()] = {}

        # process all csv files
        for statsFile in glob.glob(os.path.join(tempDir, entityType, '') + '*.csv'): # empty element in join for leading '/'
          # get file/path elements
          head, tail = os.path.split(statsFile) # path + filename (w/ extension)
          root, ext  = os.path.splitext(tail)   # filename (w/o ext) + extension
          # skip meta files
          if root == 'Meta':
            continue
          # for lowercase keys in return dict
          entityType = entityType.lower()
          # there are only normal statistics...?
          root = root.replace('.Normal', '')

          stats[entityType][root] = []

          csvReader = csv.DictReader(open(statsFile))

          # this will append all rows from the csv to our dict
          for row in csvReader:
            stats[entityType][root].append(row)

          # sum up all rows so that we get a result over all intervals
          cuRow = {}
          for columnName in csvReader.fieldnames:
            totalVal = 0

            # we don't care for these ones
            if   columnName in ['Time', 'In Service']:
              cuRow[columnName] = 'n/a'

            # rates, need to convert to float if possible
            elif columnName.endswith('/s'):
              for row in stats[entityType][root]:
                val = row[columnName]
                if not re.match('^\d+\.*\d*$', val):
                  continue
                else:
                  totalVal += float(val)
              cuRow[columnName] = totalVal/len(stats[entityType][root])

            # per-interval value, can be int or float
            else:
              for row in stats[entityType][root]:
                val = row[columnName]
                if not re.match('^\d+\.*\d*$', val):
                  continue
                else:
                  if re.match('^\d+$', val):
                    totalVal += int(val)
                  else:
                    totalVal += float(val)
              cuRow[columnName] = totalVal

          # in most cases we only want the cumulative values
          if 'cu' in returnType:
            stats[entityType][root] = cuRow

    except Exception as e:
      raise AssertionError('error proceesing csv: %s' % e.message)
    finally:
      shutil.rmtree(tempDir)

    return stats

  def startTestGroup(self):
    """
    Starts the test group on the controller.
    """
    self._execSshCommand('cli -u %s startTestGroup "//%s"' % (self._tvmcUser, self._tgName) )

  def stopTestGroup(self):
    """
    Stops the test group on the controller.
    """
    self._execSshCommand('cli -u %s stopTestGroup "//%s"' % (self._tvmcUser, self._tgName) )

  def setServiceState(self, serviceState, elementType, *elementList):
    """
    Sets the service state of a host or an application.

    - serviceState: enable|disable
    - elementType: app(lication)|host
    - elementList: _all_ or list of applications or hosts
    """
    stateDict = {
      'enable':  'In Service',
      'disable': 'Out of Service'
    }

    if elementType.lower() == 'host':
      if 'all' in elementList:
        self._execSshCommand('cli -u %s setServiceStateOfHostsInTestGroup "//%s" "%s"' % (self._tvmcUser, self._tgName, stateDict[serviceState]) )
      else:
        hostList = ','.join(map(lambda x: '"//%s//%s"' % (self._tgName, x), elementList))
        self._execSshCommand('cli -u %s setServiceStateOfHosts %s "%s"' % (self._tvmcUser, hostList, stateDict[serviceState]) )

    if 'app' in elementType.lower():
      if 'all' in elementList:
        self._execSshCommand('cli -u %s setServiceStateOfApplicationsInTestGroup "//%s" "%s"' % (self._tvmcUser, self._tgName, stateDict[serviceState]) )
      else:
        appList = ','.join(map(lambda x: '"//%s//%s"' % (self._tgName, x), elementList))
        self._execSshCommand('cli -u %s setServiceStateOfApplications %s "%s"' % (self._tvmcUser, appList, stateDict[serviceState]) )

  def _getStatistic(self, statsType, entityType, name, columnLabel, presentation):

    # see "cli help ColumnLabels"

    if   presentation == 'rate':
      columnLabel = columnLabel.strip() + '/s'
    elif 'cu' in presentation:
      columnLabel = columnLabel.strip() + ' cu'
    elif 'int' in presentation:
      columnLabel = columnLabel.strip()
    else:
      raise AssertionError('unknown presentation value: %s' % presentation)

    stat = self._execSshCommand('cli -u %s getStat %s "%s" %s %s' % (self._tvmcUser, name, columnLabel, statsType.title(), entityType.title()))

    # try to convert to integer/float
    if   re.match('^\d+$', stat):
      stat = int(stat)
    elif re.match('^\d+\.\d+$', stat):
      stat = float(stat)
    else:
      stat = stat.strip()

    return stat

  def getNormalStatistic(self, entityType, name, columnLabel, presentation):
    """
    Gets a normal statistic value from an entity specified by _name_
    - entityType: aggregate|host|application|interface|card
    - name: string
    - columnLabel: desired statistic, see gui column labels (without metric, e.g. /s)
    - presentation: rate|cu(multative)|(per-)int(erval)
    """
    return self._getStatistic( 'normal', entityType, name, columnLabel, presentation)

  def getFineStatistic(self, entityType, name, columnLabel, presentation):
    """
    Gets a fine statistic value from an entity specified by _name_
    - entityType: aggregate|host|application|interface|card
    - name: string
    - columnLabel: desired statistic, see gui column labels (without metric, e.g. /s)
    - presentation: rate|cu(multative)|(per-)int(erval)
    """
    return self._getStatistic('fine', entityType, name, columnLabel, presentation)

  ### perl related stuff

  def createExternalHost(self, name, ipAddress):
    """
    Creates an external host which may be used as a gateway (needed e.g. for static direct virtual hosts)

    - name: string
    - ipAddress: ipAddress (w/o mask)
    """
    self._write('$Tg->Add(diversifEye::ExternalHost->new(name=>"%s", ip_address=>"%s"));' % (name, ipAddress))

  def createDirectVirtualHost(self,
    name,
    physicalInterface,
    ipAddress='',
    gatewayHost='',
    macAddressAssignmentMode='specific',
    macAddress='',
    ipAssignmentType='Static',
    dhcp4Config='',
    pppoeSettings='',
    outerVlanId='',
    outerVlanPrio='0',
    innerVlanId='',
    innerVlanPrio='0',
    normalStats='true',
    fineStats='false',
    dhcpStats='false',
    pppoeStats='false',
    mtu='1492',
    startAfter='0',
    stopAfter='',
    activityCycles='false',
    activeDuration='',
    inactiveDuration='',
    scaleFactor='0'
    ):
    """
    Creates a direct virtual host which may be used by applications.

    - name: string
    - physicalInterface: interface string, e.g. 3/1/0, use comma separated value to specify multiple interfaces for scaled mode
    - ipAddress: IpAddress, will be scaled if scaleFactor > 0
    - gatewayHost: name of host created with _createExternalHost_
    - macAddressAssignmentMode: auto (auto Generate MAC From Base Value), Specific (Use Specific MAC Address), interface (Use MAC of Assigned Interface), default: specific (auto when scaleFactor is used)
    - macAddress: mac address to use if _macAddressAssignmentMode_ is set to _specific_ or base value if mode is _auto_ and scaleFactor is set
    - ipAssignmentType: Static, DHCPv4, PPPoE/IPv4CP, DHCPv6
    - dhcp4Config: dhcp4Config created with _createDhcp4Config_ which shall be used if _ipAssignmentType_ is set to _DHCPv4_
    - pppoeSettings: pppoeSettings created with _createPppoeSettings_ which shall be used if _ipAssignmentType_ is set to _PPPoE/IPv4CP_
    - outerVlanId: int, default: empty (do not create outer tag). If scaleFactor is used, use comma separated string "vlanId,incrementSize,incrementStep"
    - outerVlanPrio: int, default: 0
    - innerVlanId: int, default: empty (do not create inner tag). If scaleFactor is used, use comma separated string "vlanId,incrementSize,incrementStep"
    - innerVlanPrio: int, default: 0
    - normalStats: true|false, default: true
    - fineStats: true|false, default: false
    - dhcpStats: true|false, default: false
    - pppoeStats: true|false, default: false
    - mtu: int, default: 1492
    - startAfter: int(seconds), default: 0
    - stopAfter: int(seconds), default: empty
    - activityCycles: true|false, default: false (activity cycles disabled)
    - activeDuration: int(seconds), default: empty
    - inactiveDuration: int(seconds), default: empty
    - scaleFactor: int, default: 0 (disable scaling)

    scale outer vlan, vlan 100-104
    | createDirectVirtualHost | scaleFactor=5 | outerVlanId=100,1,1 |

    scale inner vlan, keep outer vlan 100, inner vlan 200-204
    | createDirectVirtualHost | scaleFactor=5 | outerVlanId=100,0,1 | innerVlanId=200,1,1 |

    scale mac addresses from 00:6C:D0:01:00:00 to 00:6C:D0:01:00:04
    | createDirectVirtualHost | scaleFactor=5 | macAddressAssignmentMode=auto | macAddress=00:6C:D0:01:00:00 |
    | createDirectVirtualHost | scaleFactor=5 | macAddress=00:6C:D0:01:00:00 |

    scale interfaces:
    | createDirectVirtualHost | scaleFactor=5 | physicalInterface=3/1/0,3/1/1,3/1/2 |
    """

    macAddressAssignmentModeDict = {
      'auto':       'Auto Generate MAC From Base Value',
      'specific':   'Use Specific MAC Address',
      'interface':  'Use MAC of Assigned Interface',
    }

    # scale factor settings
    if scaleFactor != '0':
      name      = '$PsAlnum->new(prefix_label=>"%s")'   % name
      ipAddress = '$PsIpa->new(start_ip_address=>"%s")' % ipAddress

      if macAddressAssignmentMode == 'specific':
        macAddressAssignmentMode = 'auto'

      if macAddressAssignmentMode == 'auto':
        macAddress = '$PsMac->new(start_mac_address=>"%s")' % macAddress
      else:
        macAddress = '$PsMacFromIf->new()'

      if len(physicalInterface.split(',')) > 1:
        physicalInterface = '$PsIfl->new(values=>"%s")' % physicalInterface
      else:
        physicalInterface = '"%s"' % physicalInterface

      if len(outerVlanId.split(',')) > 1:
        outerVlanId = '$PsVlanId->new(start=>"%s", increment_size=>"%s", increment_step=>"%s")' % tuple(outerVlanId.split(','))
      else:
        outerVlanId = '"%s"' % outerVlanId

      if len(innerVlanId.split(',')) > 1:
        innerVlanId = '$PsVlanId->new(start=>"%s", increment_size=>"%s", increment_step=>"%s")' % tuple(innerVlanId.split(','))
      else:
        innerVlanId = '"%s"' % innerVlanId

    else:
      name              = '"%s"' % name
      ipAddress         = '"%s"' % ipAddress
      macAddress        = '"%s"' % macAddress
      physicalInterface = '"%s"' % physicalInterface
      outerVlanId       = '"%s"' % outerVlanId
      innerVlanId       = '"%s"' % innerVlanId

    # create perl command
    cmd  = '$Tg->Add(diversifEye::DirectVirtualHost->new('
    cmd += ' name=>%s,'                          % name
    cmd += ' ip_address=>%s,'                    % ipAddress
    cmd += ' gateway_host=>"%s",'                % gatewayHost
    cmd += ' mac_address_assignment_mode=>"%s",' % macAddressAssignmentModeDict[macAddressAssignmentMode]
    cmd += ' mac_address=>%s,'                   % macAddress
    cmd += ' physical_interface=>%s,'            % physicalInterface
    cmd += ' ip_assignment_type=>"%s",'          % ipAssignmentType
    cmd += ' mtu=>"%s",'                         % mtu
    cmd += ' vlan_id_outer=>%s,'                 % outerVlanId
    cmd += ' vlan_priority_outer=>"%s",'         % outerVlanPrio
    cmd += ' vlan_id_inner=>%s,'                 % innerVlanId
    cmd += ' vlan_priority_inner=>"%s",'         % innerVlanPrio
    cmd += ' host_normal_stats_enabled=>"%s",'   % normalStats.lower()
    cmd += ' host_fine_stats_enabled=>"%s",'     % fineStats.lower()
    cmd += ' dhcp_stats_enabled=>"%s",'          % dhcpStats.lower()
    cmd += ' pppoe_stats_enabled=>"%s",'         % pppoeStats.lower()
    cmd += ' dhcp_configuration=>%s,'            % ( '$%s' % dhcp4Config   if dhcp4Config   else '""' )
    cmd += ' pppoe_settings=>%s,'                % ( '$%s' % pppoeSettings if pppoeSettings else '""' )
    cmd += ' start_after_delay=>"%s",'           % startAfter
    cmd += ' stop_after_time=>"%s ",'            % stopAfter
    cmd += ' enable_activity_cycles=>"%s",'      % activityCycles.lower()
    cmd += ' active_duration=>"%s",'             % activeDuration
    cmd += ' enable_inactive_duration=>"%s",'    % ( 'true' if inactiveDuration else 'false' )
    cmd += ' inactive_duration=>"%s",'           % inactiveDuration
    cmd += ' scale_factor=>"%s"'                 % scaleFactor
    cmd += '));'

    self._write(cmd)

  def createPingApp(self,
    name,
    host,
    ipAddress,
    packetSize='64',
    delayBetweenPings='1',
    startAfter='',
    stopAfter='',
    scaleFactor='0'
    ):
    """
    Creates a Ping application wich will allow a host to ping a IP address.

    - name: string
    - host: string, host for this ping application
    - IpAddress: IpAddress to ping
    - packetSize: int, default: 64
    - delayBetweenPings: int, default: 1, metric: seconds
    - startAfter: int, default: empty (not used), metric: seconds
    - stopAfter: int, default: empty (not used), metric: seconds
    """

    if scaleFactor != '0':
      provisioningMode = 'Scaled Entity'
      name = '$PsAlnum->new(prefix_label=>"%s")' % name
    else:
      provisioningMode = 'Single App per Row'
      name = '"%s"' % name

    cmd  = '$Tg->Add(diversifEye::PingApp->new('
    cmd += ' name=>%s,'                          % name
    cmd += ' host=>"%s",'                        % host
    cmd += ' ping_ip_address=>"%s",'             % ipAddress
    cmd += ' packet_size=>"%s",'                 % packetSize
    cmd += ' delay_between_pings=>"%s",'         % delayBetweenPings
    cmd += ' provisioning_mode=>"%s",'           % provisioningMode
    cmd += ' start_after=>"%s",'                 % startAfter
    cmd += ' stop_after=>"%s",'                  % stopAfter
    cmd += ' scale_factor=>"%s"'                 % scaleFactor
    cmd += '));'

    self._write(cmd)

  def createDhcp4Config(self, name):
    """
    Creates a DHCPv4 configuration for use with a (client) host. Currently uses default values.
    """
    cmd  = 'my $%s = diversifEye::Dhcp4Config->new(' % name
    cmd += ' dhcp_options=>diversifEye::Dhcp4Options->new()->Set()'
    cmd += ');'

    self._write(cmd)

  def createDhcp4Server(self, name, host, subnet, startIpAddress, numberOfIpAddresses='1'):
    """
    Creates a DHCPv4 server application.

    - name: string
    - host: string, host for this dhcp server
    - subnet: IpAddress/mask, the subnet in which to allocate IP addresses
    - startIpAddress: ipAddress, first ip address from pool
    - numberOfIpAddresses: int, default: 1
    """
    cmd  = '$Tg->Add(diversifEye::Dhcp4Server->new('
    cmd += ' name=>"%s",'                        % name
    cmd += ' host=>"%s",'                        % host
    cmd += ' subnet=>"%s",'                      % subnet
    cmd += ' start_ip_addr=>"%s",'               % startIpAddress
    cmd += ' number_of_ip_addr=>"%s"'            % numberOfIpAddresses
    cmd += '));'

    self._write(cmd)

  def createPppoeSettings(self,
    name,
    username='',
    password='',
    serviceName='',
    accessConcentrator='',
    mru='1492',
    usePap='false',
    useChap='false'
    ):
    """
    Creates a PPPoE config for use with PPPoE (client and server) hosts. The same config may be used for
    a server as well as clients.

    - name: string
    - username: string, default: empty
    - password: string, default: empty
    - serviceName: string, default: empty
    - accessConcentrator: string, default: empty
    - mru: int, default: 1492
    - usePap: true|false, default: false
    - useChap: true|false, default: false
    """
    cmd  = 'my $%s = diversifEye::PppoeSettings->new('  % name
    cmd += ' username=>"%s",'                           % username
    cmd += ' password=>"%s",'                           % password
    cmd += ' service_name=>"%s",'                       % serviceName
    cmd += ' access_concentrator=>"%s",'                % accessConcentrator
    cmd += ' mru=>"%s",'                                % mru
    cmd += ' is_pap_authentication_supported=>"%s",'    % usePap.lower()
    cmd += ' is_chap_authentication_supported=>"%s"'    % useChap.lower()
    cmd += ');'

    self._write(cmd)

  def createPppoeServer(self,
    name,
    host,
    pppoeSettings,
    startSessionId='1',
    startIp='',
    numberOfIpAddresses='100',
    startAfter='0',
    stopAfter=''
    ):
    """
    - name: string
    - host: string, host for this pppoe server
    - pppoeSettings: pppoeSettings object created with _createPppoeSettings_
    - startSessionId; int. default: 1
    - startIp: IpAddress/Mask
    - numberOfIpAddresses: int, default: 100
    """
    cmd  = '$Tg->Add(diversifEye::PppoeServer->new('
    cmd += ' name=>"%s",'                               % name
    cmd += ' host=>"%s",'                               % host
    cmd += ' pppoe_settings=>$%s,'                      % pppoeSettings
    cmd += ' start_session_id=>"%s",'                   % startSessionId
    cmd += ' ipcp_start_ip_address=>"%s",'              % startIp
    cmd += ' ipcp_no_of_available_ip_addresses=>"%s",'  % numberOfIpAddresses
    cmd += ' start_after=>"%s",'                        % startAfter
    cmd += ' stop_after=>"%s"'                          % stopAfter
    cmd += '));'

    self._write(cmd)

  def createTeraFlowServer(self,
    name,
    host,
    protocol='tcp',
    birectionalTraffic='false',
    transportPort='5001',
    normalStats='true',
    fineStats='false',
    qos='0',
    startAfter='0',
    stopAfter=''
    ):
    """
    TODO: docs
    """
    cmd  = '$Tg->Add(diversifEye::TeraFlowServer->new('
    cmd += ' name=>"%s",'                             % name
    cmd += ' host=>"%s",'                             % host
    cmd += ' protocol=>"%s",'                         % protocol.upper()
    cmd += ' is_bidirectional_traffic_enabled=>"%s",' % birectionalTraffic.lower()
    cmd += ' is_normal_stats_enabled=>"%s",'          % normalStats.lower()
    cmd += ' is_fine_stats_enabled=>"%s",'            % fineStats.lower()
    cmd += ' transport_port=>"%s",'                   % transportPort
    cmd += ' qos=>"%s",'                              % qos
    cmd += ' start_after=>"%s",'                      % startAfter
    cmd += ' stop_after=>"%s"'                        % stopAfter
    cmd += '));'

    self._write(cmd)

  def createTeraFlowClient(self,
    name,
    host,
    server,
    throughput,
    throughputMetric='Mbit/s',
    payloadSize='1024',
    transportPort='',
    normalStats='true',
    fineStats='false',
    qos='0',
    startAfter='0',
    stopAfter=''
  ):
    """
    - name: string
    - host: string, host for this application
    - server: string, TeraFlowServer to use
    - throughput: int
    - throughputMetric: bit/s, kbit/s, Mbit/s, Gbit/s, Tbit/s, default: Mbit/s
    - payloadSize: int, default: 1024
    - transportPort: int, default: empty (use next available port)
    - normalStats: true|false, default: true
    - fineStats: true|false, default: false
    - qos: int, default: 0
    """
    cmd  = '$Tg->Add(diversifEye::TeraFlowClient->new('
    cmd += ' name=>"%s",'                             % name
    cmd += ' host=>"%s",'                             % host
    cmd += ' server=>"%s",'                           % server
    cmd += ' throughput=>"%s",'                       % throughput
    cmd += ' throughput_metric=>"%s",'                % throughputMetric
    cmd += ' payload_size=>"%s",'                     % payloadSize
    cmd += ' is_normal_stats_enabled=>"%s",'          % normalStats.lower()
    cmd += ' is_fine_stats_enabled=>"%s",'            % fineStats.lower()
    cmd += ' transport_port=>"%s",'                   % transportPort
    cmd += ' qos=>"%s",'                              % qos
    cmd += ' start_after=>"%s",'                      % startAfter
    cmd += ' stop_after=>"%s"'                        % stopAfter
    cmd += '));'

    self._write(cmd)

  def createFtpServerResourceList(self, name, *resourceList):
    """
    Creates a resource list for a ftp server.
    - name: string
    - *resourceList: list of strings containing the path and size of a file. Both values are separated by a space; the size is given in bytes.

    | createFtpServerResourceList | myResourceList | /myFirstFile 1000000 | /myFolder/mySecondFile 200000 |
    """
    cmd  = 'my $%s = diversifEye::FtpResourceList->new(name=>"%s");' % (name, name)

    for resource in resourceList:
      tmp  = resource.strip().rsplit(' ', 1)

      if len(tmp) != 2:
        raise AssertionError('invalid resource; must be path and size, separated by a space')

      path = tmp[0].strip()
      size = tmp[1].strip()

      cmd += '$%s->Add(diversifEye::FtpResource->new(' % name
      cmd += ' type=>"Fixed Size",'
      cmd += ' path=>"%s",'   % path
      cmd += ' value=>"%s"'   % size
      cmd += '));'

    cmd += '$Tg->Add($%s);' % name

    self._write(cmd)

  def createFtpServer(self,
    name,
    host,
    resourceList='',
    transportPort='21',
    dataPort='',
    inactivityTimeout='900',
    normalStats='true',
    fineStats='false',
    qos='0',
    startAfter='0',
    stopAfter=''
  ):
    """
    TODO: docs
    """
    cmd  = '$Tg->Add(diversifEye::FtpServer->new('
    cmd += ' name=>"%s",'                             % name
    cmd += ' host=>"%s",'                             % host
    cmd += ' file_list=>"%s",'                        % resourceList
    cmd += ' transport_port=>"%s",'                   % transportPort
    cmd += ' data_ports=>"%s",'                       % dataPort
    cmd += ' inactivity_timeout=>"%s",'               % inactivityTimeout
    cmd += ' is_normal_stats_enabled=>"%s",'          % normalStats.lower()
    cmd += ' is_fine_stats_enabled=>"%s",'            % fineStats.lower()
    cmd += ' qos=>"%s",'                              % qos
    cmd += ' start_after=>"%s",'                      % startAfter
    cmd += ' stop_after=>"%s"'                        % stopAfter
    cmd += '));'

    self._write(cmd)

  def createFtpClientCommandList(self, name, *commandList):
    """
    Creates a resource list for a ftp server.
    - name: string
    - *commandList: list of strings containing the type of the command and the path of a file. Both values are separated by a space.

    | createFtpClientCommandList | myCommandList | get /myFirstFile | get /myFolder/mySecondFile |
    """
    cmd  = 'my $%s = diversifEye::FtpCommandList->new(name=>"%s");' % (name, name)

    for command in commandList:
      tmp  = command.strip().rsplit(' ', 1)

      if len(tmp) != 2:
        raise AssertionError('invalid command; must be type and path, separated by a space')

      type = tmp[0].strip()
      path = tmp[1].strip()

      cmd += '$%s->Add(diversifEye::FtpCommand->new(' % name
      cmd += ' type=>"%s",'   % type.lower()
      cmd += ' path=>"%s",'   % path
      cmd += '));'

    cmd += '$Tg->Add($%s);' % name

    self._write(cmd)

  def createFtpClient(self,
    name,
    host,
    server,
    commandList='',
    username='',
    password='',
    transportPort='',
    dataPort='',
    ftpMode='passive',
    normalStats='true',
    fineStats='false',
    qos='0',
    startAfter='0',
    stopAfter=''
  ):
    """
    TODO: docs
    """
    cmd  = '$Tg->Add(diversifEye::FtpClient->new('
    cmd += ' name=>"%s",'                             % name
    cmd += ' host=>"%s",'                             % host
    cmd += ' server=>"%s",'                           % server
    cmd += ' command_list=>"%s",'                     % commandList
    cmd += ' is_anonymous_enabled=>"%s",'             % ( 'false' if username and password else 'true' )
    cmd += ' username=>"%s",'                         % username
    cmd += ' password=>"%s",'                         % password
    cmd += ' transport_port=>"%s",'                   % transportPort
    cmd += ' data_ports=>"%s",'                       % dataPort
    cmd += ' ftp_mode=>"%s",'                         % ftpMode.title()
    cmd += ' is_normal_stats_enabled=>"%s",'          % normalStats.lower()
    cmd += ' is_fine_stats_enabled=>"%s",'            % fineStats.lower()
    cmd += ' qos=>"%s",'                              % qos
    cmd += ' start_after=>"%s",'                      % startAfter
    cmd += ' stop_after=>"%s"'                        % stopAfter
    cmd += '));'

    self._write(cmd)

if __name__ == '__main__':
  import sys
  from robotremoteserver import RobotRemoteServer
  RobotRemoteServer(Shenick(sys.argv[1]),  host='', port=sys.argv[2])