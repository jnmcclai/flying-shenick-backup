#!/usr/bin/python
# coding: utf-8

import os
import re
import time
import tempfile
import paramiko
import scp
import csv
import glob
import shutil
import zipfile
from robot.libraries.BuiltIn import BuiltIn
from collections import defaultdict

# for online help: python -m robot.libdoc Shenick.py::0.0.0.0 Shenick.html

class Shenick():
  """
  Mandatory parameter:
  - tvmcIp: ipAddress of TVM-C

  Optional parameter:
  - tvmUser, default: robot

  Requirements:
  - paramiko (gentoo: "emerge paramiko", *buntu/debian: "apt-get install python-paramiko")
  - scp (gentoo/*buntu/debian: "pip install scp")
  """

  ROBOT_LIBRARY_VERSION = '0.1'
  ROBOT_LIBRARY_SCOPE   = 'GLOBAL'

  def __init__(self, tvmcIp, tvmUser='robot'):
    self._tvmcIp    = tvmcIp
    self._tvmcUser  = tvmUser
    self._sshUser   = 'cli'
    self._sshPwd    = 'diversifEye'
    self._tmpFile   = None
    self._sshClient = None
    self._tgName    = None

  def __del__(self):
    if self._tmpFile is not None:
      os.close (self._tmpFile[0])
      os.remove(self._tmpFile[1])

  def _getValueFromDict(self, value, valuesDict, strict=False):
    """
    Returns the value for a given key and dictionary. If 'strict' is set to False (default)
    it will return the given value if the key is not in the dictionary. If set to True an
    AssertionError will be thrown.
    """
    try:
      returnValue = valuesDict[value]
    except:
      if strict:
        raise AssertionError('value not found for: %s' % value)
      else:
        returnValue = value

    return returnValue

  def _getDefaultParams(self, paramDict, defaultsDict):
    returnDict = paramDict.copy()

    for key in returnDict.keys():
      if key not in defaultsDict.keys():
        print '*WARN* unknown key "%s" in paramDict, ignoring' % key
        del returnDict[key]

    for key, value in defaultsDict.iteritems():
      if not returnDict.has_key(key):
        returnDict[key] = value

    return returnDict

  def _write(self, string):
    if self._tmpFile is None:
      raise AssertionError('no test group created, please use testGroupCreate first')

    with open(self._tmpFile[1], 'a') as perlFile:
      perlFile.write(string + os.linesep + os.linesep)

  def _initPerlScript(self, tgName, lowMemory='0'):

    # close & delete old temp file
    if self._tmpFile is not None:
      os.close (self._tmpFile[0])
      os.remove(self._tmpFile[1])
    # create new temp file
    self._tmpFile = tempfile.mkstemp(prefix='shenick_')

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
    self._write('use diversifEye::PsVlan;')
    self._write('use diversifEye::PsVlanId;')
    self._write('use diversifEye::PsHost;')
    self._write('use diversifEye::TcpCharacteristics;')
    self._write('use diversifEye::Profile;')
    self._write('use diversifEye::ExternalHost;')
    self._write('use diversifEye::NetworkCharacteristics;')
    self._write('use diversifEye::BandwidthRateLimit;')
    self._write('use diversifEye::AggregateGroup;')
    self._write('use diversifEye::Aggregate;')
    self._write('use diversifEye::CardLevelConfig;')
    self._write('use diversifEye::ExternalHttpProxy;')
    self._write('use diversifEye::ExternalHttpServer;')
    self._write('use diversifEye::BodyPart;')
    self._write('use diversifEye::BodyPartList;')
    self._write('use diversifEye::HttpResource;')
    self._write('use diversifEye::HttpResourceList;')
    self._write('use diversifEye::IgmpClient;')
    self._write('use diversifEye::MulticastGroup;')
    self._write('use diversifEye::MulticastGroupList;')

    # create a test group; define name here as we need the same name to delete old test groups
    self._write('my $Tg = diversifEye::TestGroup->new(name=>"%s", LowMemory=>%s);' % (tgName, lowMemory) )

  def _createSshClient(self):
    """
    Creates a ssh client, invokes a shell and returns a channel to this shell.
    """
    try:
      client = paramiko.SSHClient()
      client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      client.connect(self._tvmcIp, username=self._sshUser, password=self._sshPwd )
      channel = client.invoke_shell(width=256)
    except:
      raise AssertionError('could not open ssh connection.')
    return client, channel

  def _reconnectSshClient(self):
    """
    Checks if a ssh client is already open and, if so, checks if it is still active.
    Otherwise a new client is started. Returns the current ssh client.
    """
    try:
      if self._sshClient.get_transport().is_active() is True:
        pass
    except:
      self._sshClient, self._sshChannel = self._createSshClient()
      self._enableDefaultCliOptions()
    finally:
      return self._sshClient, self._sshChannel

  def _scpPutFile(self, local, remote):
    client, channel = self._reconnectSshClient()
    try:
      scpClient = scp.SCPClient(client.get_transport())
      scpClient.put(local, remote)
    except:
      raise AssertionError('scp put failed.')

  def _scpGetFile(self, remote, local):
    client, channel = self._reconnectSshClient()
    try:
      scpClient = scp.SCPClient(client.get_transport())
      scpClient.get(remote, local)
    except:
      raise AssertionError('scp get failed.')

  def _execSshCommand(self, command):
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
    Enables persistent background mode if it is not enabled yet. Suggested by Shenick documentation.
    Also, disable notifications, might conflict with output of other commands.
    """
    if not 'true' in self._execSshCommand('cli available'):
      self._execSshCommand('cli start')

    # found in CLI_User_Guide.pdf but cli does not know this...
    #self._execSshCommand('cli reportNotifications false')

  def _psIpaCreate(self, startIpAddress, incrementMode='withinSpecificSubnet', incrementSize='1'):
    """
    incrementMode: withinSpecificSubnet, subnet
    """
    mappingDict = {
      'withinSpecificSubnet': 'Within Specific Subnet',
      'subnet':               'Subnet'
    }

    cmd  = '$PsIpa->new('
    cmd += ' start_ip_address=>"%s",' % startIpAddress
    cmd += ' increment_mode=>"%s",'   % self._getValueFromDict(incrementMode, mappingDict, True)
    cmd += ' increment_size=>"%s"'    % incrementSize
    cmd += ')'

    return cmd

  def _psAlnumCreate(self, prefixLabel='', suffixLabel='', startingAt='1', incrementSize='1', incrementStep='1', padding='false'):
    cmd  = '$PsAlnum->new('
    cmd += ' prefix_label=>"%s",'    % prefixLabel
    cmd += ' suffix_label=>"%s",'    % suffixLabel
    cmd += ' starting_at=>"%s",'     % startingAt
    cmd += ' increment_size=>"%s",'  % incrementSize
    cmd += ' increment_step=>"%s",'  % incrementStep
    cmd += ' padding_enabled=>"%s"'  % padding
    cmd += ')'

    return cmd

  def _psIntCreate(self, startingAt, incrementSize='1', incrementStep='1'):
    cmd  = '$PsInt->new('
    cmd += ' start=>"%s",'          % startingAt
    cmd += ' increment_size=>"%s",' % incrementSize
    cmd += ' increment_step=>"%s"'  % incrementStep
    cmd += ')'

    return cmd

  def _psVlanCreate(self, startingAt, incrementSize='1', incrementStep='1', minVlanId='0', maxVLanId='4095', direction='increment'):
    """
    :param startingAt:
    :param incrementSize:
    :param incrementStep:
    :param minVlanId:
    :param maxVLanId:
    :param direction: increment|decrement
    :return:
    """
    cmd  = '$PsVlan->new('
    cmd += ' start=>"%s",'                % startingAt
    cmd += ' increment_size=>"%s",'       % incrementSize
    cmd += ' increment_step=>"%s",'       % incrementStep
    cmd += ' min_allowed_vlan_id=>"%s",'  % minVlanId
    cmd += ' max_allowed_vlan_id=>"%s",'  % maxVLanId
    cmd += ' scaling_direction=>"%s"'     % direction.capitalize()
    cmd += ')'

    return cmd

  def _psVlanIdCreate(self, startingAt, incrementSize='1', incrementStep='1', minVlanId='0', maxVLanId='4095'):
    cmd  = '$PsVlanId->new('
    cmd += ' start=>"%s",'                % startingAt
    cmd += ' increment_size=>"%s",'       % incrementSize
    cmd += ' increment_step=>"%s",'       % incrementStep
    cmd += ' min_allowed_vlan_id=>"%s",'  % minVlanId
    cmd += ' max_allowed_vlan_id=>"%s"'   % maxVLanId
    cmd += ')'

    return cmd

  def _dhcp4ConfigCreate(self, paramDict):
    """
    Creates a DHCPv4 configuration for use with a (client) host. Currently uses default values.
    """

    """
    diversifEye::Dhcp4Config

    dhcp_options=>"" [Instance of diversifEye::Dhcp4Options]. Scalable. Suggested scalers: [PsDhcp4Options].
    offer_collection_timer=>"" [Integer].
    offer_collection_timer_metric=>"secs" [ms|secs|mins].
    lease_time=>"" [Integer].
    lease_time_metric=>"secs" [ms|secs|mins].
    renewal_time=>"" [Integer].
    renewal_time_metric=>"secs" [ms|secs|mins].
    supports_force_renew=>"false" [false|true].
    is_authentication_enabled=>"false" [false|true].
    authentication_key=>"" Scalable. Suggested scalers: [PsHex].
    authentication_key_id=>"1" Scalable. Suggested scalers: [PsLong].
    """

    """
    diversifEye::DhcpOptions

    new()
      Creates an empty instance of Dhcp4Options. Use method Set to add properties.

    Set(Name[, Value])
       Sets a single DHCPv4 option value or a set of default option values. If Name is absent, default values are set.

       Otherwise a single option is set to Value, if present. If Value is not present, the option value is set to undef
       unless Name is of a supported option, in which case a suitable default value is set.

       Value may be a scalar or a reference to an instance of DhcpOptions.  The latter is interpreted as a set of set of DHCPv4 sub-options.

       DhcpOptions does not impose any restriction on the Names or Values specified. However, the Names and Value types accepted by the diversifEye XML Importer are restricted to a subset of those
       defined in the relevant RFCs.

       Here are the options supported for DHCPv4:

       Name                        Type(Example)

       subnetmask                  IPv4 Address.
       routers                     Comma-separated list of IPv4 Addresses.
       host_name                   ASCII String.
       vendor_specific_information Octet String (even no of hex digits).
       dhcp_requested_ip_address   IPv4 Address.
       dhcp_lease_time             Unsigned 32bit decimal integer.
       server_identifier           IPv4 Address.
       dhcp_parameter_request_list Comma-separated list of unsigned 8-bit decimal integers.
       dhcp_max_message_size       Unsigned 16-bit decimal integer.
       dhcp_renewal_time           Unsigned 32-bit decimal integer.
       dhcp_rebinding_time         Unsigned 32-bit decimal integer.
       vendor_class_identifier     ASCII String.
       client_identifier           OctetString (even no of hex digits).
       auto_configure              Boolean (true│false).
       relay_agent_info            DhcpOptions reference with following sub-options:
       circuit_id                  OctetString (even no of hex digits).
       remote_id                   OctetString (use diversifEye::RemoteId).
    """

    """
    diversifEye::PsDhcp4Options

    dhcp_options=>"" [Instance of diversifEye::Dhcp4Options].
    scale_dhcp_option_61=>"true" [false|true].
    scale_dhcp_option_82=>"false" [false|true].
    circuit_ids=>"" [A reference to an array of circuit ids or a single string containing comma-separated circuit ids].
    remote_ids=>"" [A reference to an array of remote ids or a single string containing comma-separated remote ids].
    """

    if   paramDict['dhcpOptions'] == 'default':
      cmd  = 'diversifEye::Dhcp4Config->new('
      cmd += ' dhcp_options=>diversifEye::Dhcp4Options->new()->Set()'
      cmd += ')'
    elif paramDict['dhcpOptions'] == 'manual':
      raise AssertionError('dhcp config mode "manual" not implemented yet')
    else:
      raise AssertionError('unknown dhcp config mode: %s' % paramDict['mode'])

    return cmd

  def _dhcp6ConfigCreate(self, dhcpParamDict):
     raise AssertionError('not implemented yet')

  def _pppoeSettingsCreate(self, paramDict):
    """
    Creates a PPPoE config for use with PPPoE (client and server) hosts.
    """
    cmd  = 'diversifEye::PppoeSettings->new('
    cmd += ' for_ipv6=>"%s",'                             % paramDict['forIpv6']
    cmd += ' username=>"%s",'                             % paramDict['username']
    cmd += ' password=>"%s",'                             % paramDict['password']
    cmd += ' service_name=>"%s",'                         % paramDict['serviceName']
    cmd += ' access_concentrator=>"%s",'                  % paramDict['accessConcentrator']
    cmd += ' mru=>"%s",'                                  % paramDict['mru']
    cmd += ' is_pap_authentication_supported=>"%s",'      % paramDict['isPapSupported']
    cmd += ' is_chap_authentication_supported=>"%s",'     % paramDict['isChapSupported']
    cmd += ' is_checking_host_uniq=>"%s",'                % paramDict['checkHostUnique']
    cmd += ' is_ac_cookie_used=>"%s",'                    % paramDict['isAcCookieUsed']
    cmd += ' is_magic_number_used=>"%s",'                 % paramDict['isMagicNumberUsed']
    cmd += ' is_double_retransmit_time=>"%s",'            % paramDict['doubleRetransmitTime']
    cmd += ' retransmit_timer=>"%s",'                     % paramDict['retransmitTimer']
    cmd += ' retransmit_timer_metric=>"%s",'              % paramDict['retransmitTimerMetric']
    cmd += ' lcp_link_test_request_mode=>"%s",'           % paramDict['lcpLinkTestRequestMode'].capitalize()
    cmd += ' lcp_link_test_payload_size=>"%s",'           % paramDict['lcpLinkTestPayloadSize']
    cmd += ' lcp_link_test_interval=>"%s",'               % paramDict['lcpLinkTestInterval']
    cmd += ' lcp_link_test_interval_metric=>"%s",'        % paramDict['lcpLinkTestIntervalMetric']
    cmd += ' reconnect_after_failure=>"%s",'              % paramDict['reconnectAfterFailure']
    cmd += ' request_primary_dns_server_address=>"%s",'   % paramDict['requestPrimaryDns']
    cmd += ' request_secondary_dns_server_address=>"%s",' % paramDict['requestSecondaryDns']
    cmd += ')'

    return cmd

  def _externalHostCreate(self, name, paramDict):
    # scale factor settings
    if paramDict['scaleFactor']:
      name      = self._psAlnumCreate(name)
      ipAddress = self._psIpaCreate(paramDict['ipAddress'], paramDict['ipAddressIncrementMode'], paramDict['ipAddressIncrementSize'])
    else:
      name      = '"%s"' % name
      ipAddress = '"%s"' % paramDict['ipAddress']

    # create perl command
    cmd  = '$Tg->Add(diversifEye::ExternalHost->new('
    cmd += ' name=>%s,'                  % name
    cmd += ' description=>"%s",'         % paramDict['description']
    cmd += ' ip_address=>%s,'            % ipAddress
    cmd += ' scale_factor=>"%s",'        % paramDict['scaleFactor']
    cmd += ' optional_properties=>"",'
    cmd += '));'

    self._write(cmd)

  def _directVirtualHostCreate(self, name, paramDict):
    # create dhcp/pppoe settings
    if   paramDict['ipAddressAssignmentType'] == 'dhcpv4':
      dhcpConfig = self._dhcp4ConfigCreate(paramDict)
    elif paramDict['ipAddressAssignmentType'] == 'dhcpv6':
      dhcpConfig = self._dhcp6ConfigCreate(paramDict)
    else:
      dhcpConfig = '""'

    if paramDict['ipAddressAssignmentType'] == 'pppoe-ipv4cp':
      paramDict['enablePppoe'] = 'true'

    if paramDict['enablePppoe'] == 'true':
      pppoeConfig = self._pppoeSettingsCreate(paramDict)
    else:
      pppoeConfig = '""'

    # scale factor settings
    if paramDict['scaleFactor']:
      # default values
      outerVlanId = '""'
      innerVlanId = '""'
      vlanIdMulti = 1

      name = self._psAlnumCreate(name)
      if paramDict['ipAddress']:
        ipAddress = self._psIpaCreate(paramDict['ipAddress'], paramDict['ipAddressIncrementMode'], paramDict['ipAddressIncrementSize'])
      else:
        ipAddress = '""'

      if paramDict['macAddress'] == 'useInterfaceMac':
        macAddress = '$PsMacFromIf->new()'
        macAddressAssignmentMode = 'Use MAC of Assigned Interface'
      else:
        macAddress = '$PsMac->new(start_mac_address=>"%s")' % paramDict['macAddress']
        macAddressAssignmentMode = 'Auto Generate MAC From Base Value'

      if len(paramDict['physicalInterface'].split(',')) > 1:
        physicalInterface = '$PsIfl->new(values=>"%s")' % paramDict['physicalInterface']
      else:
        physicalInterface = '"%s"' % paramDict['physicalInterface']

      if len(paramDict['vni'].split(',')) > 1:
        vni = self._psIntCreate(*(paramDict['vni'].split(',')))
      else:
        vni = '"%s"' % paramDict['vni']

      if paramDict['linkLayer'] == 'taggedVlan':
        if len(paramDict['vlanIdList']) < 1: raise AssertionError('vlanIdList has no outer vlan')

        if len(paramDict['vlanIdList'][0].split(',')) > 1:
          outerVlanId = self._psVlanIdCreate(*(paramDict['vlanIdList'][0].split(',')))
        else:
          outerVlanId = '"%s"' % paramDict['vlanIdList'][0]

      if paramDict['linkLayer'] == 'doubleTaggedVlan':

        if len(paramDict['vlanIdList']) < 2: raise AssertionError('vlanIdList has no outer/inner vlan')

        if len(paramDict['vlanIdList'][0].split(',')) > 1:
          outerVlanId = self._psVlanIdCreate(*(paramDict['vlanIdList'][0].split(',')))
        else:
          outerVlanId = '"%s"' % paramDict['vlanIdList'][0]

        if len(paramDict['vlanIdList'][1].split(',')) > 1:
          innerVlanId = self._psVlanIdCreate(*(paramDict['vlanIdList'][1].split(',')))
        else:
          innerVlanId = '"%s"' % paramDict['vlanIdList'][1]

      if paramDict['linkLayer'] == 'multipleTaggedVlan':
        vlanIdMulti = '['
        for vlanId in paramDict['vlanIdList']:
          if len(vlanId.split(',')) > 1:
            vlanIdMulti += self._psVlanCreate(*(vlanId.split(',')))
          else:
            vlanIdMulti += '%s' % vlanId
          vlanIdMulti += ','
        vlanIdMulti = vlanIdMulti[:-1] + ']'

    # single host settings
    else:
      name              = '"%s"'  %  name
      ipAddress         = '"%s"'  %  paramDict['ipAddress']
      physicalInterface = '"%s"'  %  paramDict['physicalInterface']
      outerVlanId       = '"%s"'  % (paramDict['vlanIdList'][0] if len(paramDict['vlanIdList']) > 0 else '')
      innerVlanId       = '"%s"'  % (paramDict['vlanIdList'][1] if len(paramDict['vlanIdList']) > 1 else '')
      vni               = '"%s"'  %  paramDict['vni']
      vlanIdMulti       = '[%s]'  % ','.join(paramDict['vlanIdList'])

      if paramDict['macAddress'] == 'useInterfaceMac':
        macAddress = '$PsMacFromIf->new()'
        macAddressAssignmentMode = 'Use MAC of Assigned Interface'
      else:
        macAddress = '"%s"' % paramDict['macAddress']
        macAddressAssignmentMode = 'Use Specific MAC Address'

    # replace values
    paramDict['ipAddressAssignmentType'] = self._getValueFromDict(
      paramDict['ipAddressAssignmentType'],
      {
        'static':       'Static',
        'dhcpv4':       'DHCPv4',
        'dhcpv6':       'DHCPv6',
        'pppoe-ipv4cp': 'PPPoE/IPv4CP'
      },
      strict=True
    )

    paramDict['linkLayer'] = self._getValueFromDict(
      paramDict['linkLayer'],
      {
        'ethernet':           'Ethernet',
        'taggedVlan':         'Tagged Vlan',
        'doubleTaggedVlan':   'Double Tagged Vlan',
        'multipleTaggedVlan': 'Multiple Tagged Vlan',
        'vxlan':              'VXLAN',
        '':                   ''
      },
      strict=True
    )

    paramDict['serviceState'] = self._getValueFromDict(
      paramDict['serviceState'],
      {
        'inService':    'In Service',
        'outOfService': 'Out of Service'
      },
      strict=True
    )

    paramDict['advertiseRoutes'] = self._getValueFromDict(
      paramDict['advertiseRoutes'],
      {
        'disabled':     'Disabled',
        'RIPv2':        'RIPv2',
        'RIPng':        'RIPng'
      },
      strict=True
    )

    # create perl command
    cmd  = '$Tg->Add(diversifEye::DirectVirtualHost->new('
    cmd += ' name=>%s,'                               % name

    # general
    cmd += ' ip_address=>%s,'                         % ipAddress
    cmd += ' dhcp_configuration=>%s,'                 % dhcpConfig
    cmd += ' pppoe_settings=>%s,'                     % pppoeConfig
    cmd += ' description=>"%s",'                      % paramDict['description']
    cmd += ' service_state=>"%s",'                    % paramDict['serviceState']
    cmd += ' gateway_host=>"%s",'                     % paramDict['gatewayHost']
    cmd += ' ip_assignment_type=>"%s",'               % paramDict['ipAddressAssignmentType']
    cmd += ' initial_flow_label=>"%s",'               % paramDict['ipv6InitialFlowLabel']
    cmd += ' mtu_discovery=>"%s",'                    % paramDict['ipv6MtuDiscovery']
    cmd += ' block_all_traffic=>"%s",'                % paramDict['blockAllTraffic']
    cmd += ' scale_factor=>"%s",'                     % paramDict['scaleFactor']
    cmd += ' tcp_characteristics=>"%s",'              % paramDict['tcpCharacteristics']
    cmd += ' enable_voip_b2bua_support=>"%s",'        % paramDict['sipB2buaSupport']
    cmd += ' b2bua_sip_port=>"%s",'                   % paramDict['sipB2buaPort']
    cmd += ' rip_version=>"%s",'                      % paramDict['advertiseRoutes']
    cmd += ' network_characteristics=>"%s",'          % paramDict['tcpNetworkCharacteristics']
    cmd += ' inbound_bandwidth_rate_limiter=>"%s",'   % paramDict['tcpInBandwidthRateLimit']
    cmd += ' outbound_bandwidth_rate_limiter=>"%s",'  % paramDict['tcpOutBandwidthRateLimit']

    # link layer
    cmd += ' vni=>%s,'                                %  vni
    cmd += ' mac_address=>%s,'                        %  macAddress
    cmd += ' vlan_id_outer=>%s,'                      %  outerVlanId
    cmd += ' vlan_id_inner=>%s,'                      %  innerVlanId
    cmd += ' physical_interface=>%s,'                 %  physicalInterface
    cmd += ' mac_address_assignment_mode=>"%s",'      %  macAddressAssignmentMode
    cmd += ' mtu=>"%s",'                              %  paramDict['mtu']
    cmd += ' link_layer_type=>"%s",'                  %  paramDict['linkLayer']
    cmd += ' vlan_priority_outer=>"%s",'              % (paramDict['vlanPrioList'][0] if len(paramDict['vlanPrioList']) > 0 else '0')
    cmd += ' vlan_priority_inner=>"%s",'              % (paramDict['vlanPrioList'][1] if len(paramDict['vlanPrioList']) > 1 else '0')
    cmd += ' vlan_id_multi=>%s,'                      %  vlanIdMulti
    cmd += ' vlan_priority_multi=>[%s],'              % ','.join(paramDict['vlanPrioList'])

    # statistics
    cmd += ' host_normal_stats_enabled=>"%s",'        % paramDict['normalStats']
    cmd += ' host_fine_stats_enabled=>"%s",'          % paramDict['fineStats']
    cmd += ' dhcp_stats_enabled=>"%s",'               % paramDict['dhcpStats']
    cmd += ' pppoe_stats_enabled=>"%s",'              % paramDict['pppoeStats']
    cmd += ' connection_stats_enabled=>"%s",'         % paramDict['connectionStats']
    cmd += ' extended_tcp_stats_enabled=>"%s",'       % paramDict['extendedTcpStats']
    cmd += ' aggregate_group=>"%s",'                  % paramDict['aggregateGroup']

    # activity
    cmd += ' enable_activity_cycles=>"%s",'           % paramDict['enableActivityCycles']
    cmd += ' active_duration=>"%s",'                  % paramDict['activeDuration']
    cmd += ' active_duration_metric=>"%s",'           % paramDict['activeDurationMetric']
    cmd += ' enable_inactive_duration=>"%s",'         % ('true' if paramDict['inactiveDuration'] else 'false')
    cmd += ' inactive_duration=>"%s",'                % paramDict['inactiveDuration']
    cmd += ' inactive_duration_metric=>"%s",'         % paramDict['inactiveDurationMetric']
    cmd += ' enable_start_after_delay=>"%s",'         % ('true' if paramDict['startAfter'] else 'false')
    cmd += ' start_after_delay=>"%s",'                % paramDict['startAfter']
    cmd += ' start_after_delay_metric=>"%s",'         % paramDict['startAfterMetric']
    cmd += ' enable_stop_after_time=>"%s",'           % ('true' if paramDict['stopAfter'] else 'false')
    cmd += ' stop_after_time=>"%s ",'                 % paramDict['stopAfter']
    cmd += ' stop_after_time_metric=>"%s ",'          % paramDict['stopAfterMetric']

    cmd += '));'

    self._write(cmd)

  def hostCreate(self, name, paramDict=None):
    """
    Creates a host. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked *bold*):

    | *Group*               | *Key*                       | *Value*                                                    |
    | *General*             | numberOfHosts               | _*1*_ , <number [ >0 ]>                                |
    |                       | type                        | _*virtualHost*_ , _virtualSubnetHost_ , _externalHost_ , _externalSubnetHost_ |
    |                       | description                 | <string> , *empty*                                         |
    |                       | networkVisible              | _false_ , _*true*_                                         |
    |                       | ipAddressAssignmentType     | _*static*_ , _dhcpv4_ , _dhcpv6_ , _pppoe-ipv4cp_          |
    |                       | ipAddress                   | <IP address[/mask if ipAddressAssignmentType is 'static'], (*mandatory* if ipAddressAssignmentType is _static_) , *empty* |
    |                       | ipAddressIncrementMode      | _*withinSpecificSubnet*_ , _subnet_                        |
    |                       | ipAddressIncrementSize      | _*1*_ , <number>                                    |
    |                       | gatewayHost                 | <host created with type = _externalHost_ > , *empty*    |
    |                       | advertiseRoutes             | _*disabled*_ , _RIPv2_ , _RIPng_                           |
    |                       | enablePppoe                 | _*false*_ , _true_                                         |
    |                       | tcpCharacteristics          | <name of profile created with tcpCharacteristicsCreate> , *empty* |
    |                       | tcpOutBandwidthRateLimit    | <name of profile created with bandwithRateLimitCreate> , *empty* |
    |                       | tcpInBandwidthRateLimit     | <name of profile created with bandwithRateLimitCreate> , *empty* |
    |                       | tcpNetworkCharacteristics   | <name of profile created with networkCharacteristicsCreate> , *empty* |
    |                       | ipv6InitialFlowLabel        | [not implemented]                                      |
    |                       | ipv6MtuDiscovery            | [not implemented]                                      |
    |                       | sipB2buaSupport             | _*false*_ , _true_ [not implemented]                                                                          |
    |                       | sipB2buaPort                | _*5060*_ , <number>, [not implemented]                                                               |
    |                       | serviceState                | _*inService*_ , _outOfService_                                                                                   |
    |                       | blockAllTraffic             | _*false*_ , _true_                                                                                               |
    | *Link Layer setting*  | *physicalInterface*         | <interface string> , *empty* (e.g. '3/1/0', *mandatory* if type is not externalHost or externalSubnetHost) |
    |                       | macAddress                  | _*useInterfaceMac*_ , _macAddress_                                                                               |
    |                       | mtu                         | _*1500*_ , <number>                                                                                    |
    |                       | linkLayer                   | _*ethernet*_ , _taggedVlan_ , _doubleTaggedVlan_ , _multipleTaggedVlan_ , _vxlan_                                         |
    |                       | vni                         | <number [ *0* .. 16777215 ]> (used for linkLayer "vxlan")                                                |
    |                       | vlanIdList                  | <list of numbers [ *0* .. 4095 ]> , *empty* (up to 6 values for linkLayer "multipleTaggedVlan")          |
    |                       | vlanPrioList                | <list of numbers [ *0* .. 7 ]>  (if multipleTaggedVlan is selected, the last value is repeated if there are fewer elements in 'vlanPrioList' than in 'vlanIdList') |
    | *Dhcp setting*        | dhcpOptions                 | _*default*_ , _manual_                                                                                                  |
    | *PPPoE settings*      | forIpv6                     | _*false*_ , _true_                                                                                               |
    |                       | username                    | <string> , _PsAlnum_ [not implemented], *empty*                                                         |
    |                       | password                    | <string> , _PsAlnum_ [not implemented], *empty*                                                         |
    |                       | serviceName                 | <string> , _PsAlnum_ [not implemented], *empty*                                                         |
    |                       | accessConcentrator          | <string> , _PsAlnum_ [not implemented], *empty*                                                         |
    |                       | mru                         | _*1500*_ , <number>                                                                                     |
    |                       | isPapSupported              | _*false*_ , _true_                                                                                               |
    |                       | isChapSupported             | _*false*_ , _true_                                                                                               |
    |                       | checkHostUnique             | _false_ , _*true*_                                                                                               |
    |                       | isAcCookieUsed              | _false_ , _*true*_                                                                                               |
    |                       | isMagicNumberUsed           | _false_ , _*true*_                                                                                               |
    |                       | doubleRetransmitTime        | _*false*_ , _true_                                                                                               |
    |                       | retransmitTimer             | _*3000*_ , <number>                                                                                    |
    |                       | retransmitTimerMetric       | _*ms*_ , _secs_ , _mins_                                                                                            |
    |                       | lcpLinkTestRequestMode      | _*none*, echo, discard_                                                                                       |
    |                       | lcpLinkTestPayloadSize      | _*1492*_ , <number>                                                                                    |
    |                       | lcpLinkTestInterval         | _*30*_ , <number>                                                                                      |
    |                       | lcpLinkTestIntervalMetric   | _ms, *secs*, mins_                                                                                            |
    |                       | reconnectAfterFailure       | _false_ , _*true*_                                                                                               |
    |                       | requestPrimaryDns           | _*false*_ , _true_                                                                                               |
    |                       | requestSecondaryDns         | _*false*_ , _true_                                                                                               |
    | *Statistics*          | normalStats                 | _false_ , _*true*_                                                                                               |
    |                       | fineStats                   | _*false*_ , _true_                                                                                               |
    |                       | dhcpStats                   | _*false*_ , _true_                                                                                               |
    |                       | pppoeStats                  | _*false*_ , _true_                                                                                               |
    |                       | connectionStats             | _*false*_ , _true_                                                                                               |
    |                       | extendedTcpStats            | _*false*_ , _true_                                                                                               |
    |                       | aggregateGroup              | <name of aggregate group created with aggregateGroupCreate> , _*Default*_                       |
    | *Activity settings*   | enableActivityCycles        | _*false*_ , _true_                                                                                               |
    |                       | activeDuration              | <number> , <name of profile created with probabilityDistributionCreate> , *empty*                      |
    |                       | activeDurationMetric        | _*secs*_ , _mins_ , _hrs_                                                                                           |
    |                       | inactiveDuration            | <number> , <name of profile created with probabilityDistributionCreate> , *empty*                      |
    |                       | inactiveDurationMetric      | _*secs*_ , _mins_ , _hrs_                                                                                           |
    |                       | startAfter                  | <number> , <name of profile created with probabilityDistributionCreate> , *empty*                      |
    |                       | startAfterMetric            | _*ms*_ , _secs_ , _mins_                                                                                            |
    |                       | stopAfter                   | <number> , <name of profile created with probabilityDistributionCreate> , *empty*                      |
    |                       | stopAfterMetric             | _*secs*_ , _mins_ , _hrs_                                                                                           |

    *Note*: doubleTaggedVlan + scaled => all vlans must be either scaled or not scaled, and must not be mixed, otherwise scaled vlan will get non-scaled
    """
    # we accept dictionaries only
    paramDict = {} if type(paramDict) is not dict else paramDict

    defaultParamDict = {
      'description':                '',                     # string
      'numberOfHosts':              '1',                    # int
      'type':                       'virtualHost',          # virtualHost, virtualSubnetHost, externalHost, externalSubnetHost
      'networkVisible':             'true',                 # true, false
      'ipAddressAssignmentType':    'static',               # static, dhcpv4, dhcpv6, pppoe-ipv4cp
      'ipAddress':                  '',                     # ipAddress
      'ipAddressIncrementMode':     'withinSpecificSubnet', # withinSpecificSubnet, subnet
      'ipAddressIncrementSize':     '1',                    # int
      'gatewayHost':                '',                     # string, name of host created with type=externalHost
      'advertiseRoutes':            'disabled',             # disabled, RIPv2, RIPng
      'enablePppoe':                'false',                # true, false
      'tcpCharacteristics':         '',                     # string, name of profile created with _tcpCharacteristicsCreate_
      'tcpOutBandwidthRateLimit':   '',                     # string, name of profile created with _bandwithRateLimitCreate_
      'tcpInBandwidthRateLimit':    '',                     # string, name of profile created with _bandwithRateLimitCreate_
      'tcpNetworkCharacteristics':  '',                     # string, name of profile created with _networkCharacteristicsCreate_
      'ipv6InitialFlowLabel':       '',                     # not implemented yet
      'ipv6MtuDiscovery':           '',                     # not implemented yet
      'sipB2buaSupport':            'false',                # not implemented yet
      'sipB2buaPort':               '5060',                 # not implemented yet
      'serviceState':               'inService',            # inService, outOfService
      'blockAllTraffic':            'false',                # true, false
      'physicalInterface':          '',
      'macAddress':                 'useInterfaceMac',      # useInterfaceMac, macAddress, e.g. 00:01:02:03:04:05
      'mtu':                        '1500',                 # int
      'linkLayer':                  'ethernet',             # ethernet, taggedVlan, doubleTaggedVlan, multipleTaggedVlan, vxlan
      'vni':                        '0',                    # int 0-16777215, used for vxlan
      'vlanIdList':                 [],                     # list of integers, 0-4095, up to 6 values for multipleTaggedVlan
      'vlanPrioList':               ['0'],                  # list of integers, 0-7, up to 6 values for multipleTaggedVlan.
                                                            # if multipleTaggedVlan is selected, the last value is repeated if there are fewer
                                                            # elements in 'vlanPrioList' than in 'vlanIdList'. Else the default priority is '0'
      'dhcpOptions':                'default',              # default, manual
      'forIpv6':                    'false',                # true, false
      'username':                   '',                     # string, PsAlnum (not implemented)
      'password':                   '',                     # string, PsAlnum (not implemented)
      'serviceName':                '',                     # string, PsAlnum (not implemented)
      'accessConcentrator':         '',                     # string, PsAlnum (not implemented)
      'mru':                        '1492',                 # int
      'isPapSupported':             'false',                # true, false
      'isChapSupported':            'false',                # true, false
      'checkHostUnique':            'true',                 # true, false
      'isAcCookieUsed':             'true',                 # true, false
      'isMagicNumberUsed':          'true',                 # true, false
      'doubleRetransmitTime':       'false',                # true, false
      'retransmitTimer':            '3000',                 # int
      'retransmitTimerMetric':      'ms',                   # ms, secs, mins
      'lcpLinkTestRequestMode':     'none',                 # none, echo, discard
      'lcpLinkTestPayloadSize':     '1492',                 # int
      'lcpLinkTestInterval':        '30',                   # int
      'lcpLinkTestIntervalMetric':  'secs',                 # ms, secs, mins
      'reconnectAfterFailure':      'true',                 # true, false
      'requestPrimaryDns':          'false',                # true, false
      'requestSecondaryDns':        'false',                # true, false
      'normalStats':                'true',                 # true, false, psBool (not implemented)
      'fineStats':                  'false',                # true, false, psBool (not implemented)
      'dhcpStats':                  'false',                # true, false
      'pppoeStats':                 'false',                # true, false
      'connectionStats':            'false',                # true, false
      'extendedTcpStats':           'false',                # true, false
      'aggregateGroup':             'Default',              # string, name of aggregate group created with _aggregateGroupCreate_
      'enableActivityCycles':       'false',                # true, false
      'activeDuration':             '',                     # int, name of profile created with _propabilityDistributionCreate_
      'activeDurationMetric':       'secs',                 # secs, mins, hrs
      'inactiveDuration':           '',                     # int, name of profile created with _propabilityDistributionCreate_
      'inactiveDurationMetric':     'secs',                 # secs, mins, hrs
      'startAfter':                 '',                     # int, name of profile created with _propabilityDistributionCreate_
      'startAfterMetric':           'ms',                   # ms, secs, mins
      'stopAfter':                  '',                     # int, name of profile created with _propabilityDistributionCreate_
      'stopAfterMetric':            'secs',                 # secs, mins, hrs
    }

    paramDict    = self._getDefaultParams(paramDict, defaultParamDict)

    # add scaleFactor as only this is important
    paramDict['scaleFactor'] = ('' if paramDict['numberOfHosts'] == '1' else paramDict['numberOfHosts'])

    # vlanIdList and vlanPrioList should only contain strings
    paramDict['vlanIdList']   = map(lambda x: str(x), paramDict['vlanIdList'])
    paramDict['vlanPrioList'] = map(lambda x: str(x), paramDict['vlanPrioList'])

    if   paramDict['type'] == 'externalHost':
      self._externalHostCreate(name, paramDict)

    elif paramDict['type'] == 'virtualHost':
      self._directVirtualHostCreate(name, paramDict)

    else:
      raise AssertionError('unknown type: %s' % paramDict['type'])

  def tcpCharacteristicsCreate(self, name, paramDict=None):
    """
    Creates a TCP characteristics profile. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked *bold*):

    | *Group*               | *Key*                       | *Value*                                                               |
    | *General*             | description                 | <string> , *empty*                                            |
    | *TCP parameters*      | maxTransmitBufferSize       | <number [ >0 ]> , *empty*                                     |
    |                       | maxAdvertRecvWindowSize     | <number [ 1 .. 65535 ]> , *empty*                                 |
    |                       | initialRetransTimeout       | <number [ 1 .. 600000 ]> , *empty*                                |
    |                       | tcpTimer                    | <number [ 10 .. 500 ]> , <<probability distribution profile created with probabilityDistributionCreate>> , *empty* |
    | *TCP behaviour*       | emulateDelayedAcks          | _*allSegments*_ , _max2Segments_ , _off_                                    |
    |                       | firstSegmentAckSynAck       | _*false*_ , _true_                                                       |
    |                       | finalSegmentIncFin          | _false_ , _*true*_                                                       |
    |                       | finalSegmentAckIncFin       | _false_ , _*true*_                                                       |
    | *TCP options*         | maxSegmentSize              | <number [1 .. 1460 ]> , <<probability distribution profile created with probabilityDistributionCreate>> , *empty* |
    |                       | windowScale                 | <number [0 .. 14 ]> , *empty*_                                    |
    |                       | useSackWhenPermitted        | _*false*_ , _true_                                                       |
    |                       | setSackPermitted            | _*false*_ , _true_                                                       |
    |                       | suppTimestampWhenReq        | _*false*_ , _true_                                                       |
    |                       | reqTimestamp                | _*false*_ , _true_                                                       |
    """
    # we accept dictionaries only
    paramDict = {} if type(paramDict) is not dict else paramDict

    defaultDict = {
      'description':             '',              # string
      'maxTransmitBufferSize':   '',              # Empty|Integer(>=1). Bytes
      'maxAdvertRecvWindowSize': '',              # Empty|Integer(1-65535). Bytes
      'initialRetransTimeout':   '',              # Empty|Integer(1-600000). Milliseconds
      'tcpTimer':                '',              # Empty|Profile|Integer(10-500). Milliseconds
      'emulateDelayedAcks':      'allSegments',   # All Segments|Max. 2 Segments| Off, translation below
      'firstSegmentAckSynAck':   'false',         # false|true
      'finalSegmentIncFin':      'true',          # false|true
      'finalSegmentAckIncFin':   'true',          # false|true
      'maxSegmentSize':          '',              # Empty|Profile|Integer(1-1460). Bytes
      'windowScale':             '',              # Empty|0|1|2|3|4|5|6|7|8|9|10|11|12|13|14
      'useSackWhenPermitted':    'false',         # false|true
      'setSackPermitted':        'false',         # false|true
      'suppTimestampWhenReq':    'false',         # false|true
      'reqTimestamp':            'false',         # false|true
    }

    paramDict = self._getDefaultParams(paramDict, defaultDict)

    paramDict['emulateDelayedAcks'] = self._getValueFromDict(paramDict['emulateDelayedAcks'], {
                                        'allSegments':  'All Segments',
                                        'max2Segments': 'Max. 2 Segments',
                                        'off':          'Off'
                                      }, strict=True)

    # create perl command
    cmd  = '$Tg->Add(diversifEye::TcpCharacteristics->new('
    cmd += ' name=>"%s",'                                     % name
    cmd += ' description=>"%s",'                              % paramDict['description']
    cmd += ' tcp_profile_max_transmit_buffer_size=>"%s",'     % paramDict['maxTransmitBufferSize']
    cmd += ' tcp_profile_max_advert_recv_window_size=>"%s",'  % paramDict['maxAdvertRecvWindowSize']
    cmd += ' tcp_profile_initial_retrans_timeout=>"%s",'      % paramDict['initialRetransTimeout']
    cmd += ' tcp_timer_profile=>"%s",'                        % paramDict['tcpTimer']
    cmd += ' tcp_profile_emulate_delayed_acks=>"%s",'         % paramDict['emulateDelayedAcks']
    cmd += ' tcp_profile_first_segment_ack_syn_ack=>"%s",'    % paramDict['firstSegmentAckSynAck']
    cmd += ' tcp_profile_final_segment_inc_fin=>"%s",'        % paramDict['finalSegmentIncFin']
    cmd += ' tcp_profile_final_segment_ack_inc_fin=>"%s",'    % paramDict['finalSegmentAckIncFin']
    cmd += ' tcp_profile_max_segment_size=>"%s",'             % paramDict['maxSegmentSize']
    cmd += ' tcp_window_scale=>"%s",'                         % paramDict['windowScale']
    cmd += ' tcp_profile_use_sack_when_permitted=>"%s",'      % paramDict['useSackWhenPermitted']
    cmd += ' tcp_profile_set_sack_permitted=>"%s",'           % paramDict['setSackPermitted']
    cmd += ' tcp_supp_timestamp_when_req=>"%s",'              % paramDict['suppTimestampWhenReq']
    cmd += ' tcp_req_timestamp=>"%s",'                        % paramDict['reqTimestamp']
    cmd += '));'

    self._write(cmd)

  def networkCharacteristicsCreate(self, name, paramDict=None):
    """
    Creates a network characteristics profile. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked *bold*):

    | *Group*                 | *Key*                       | *Value*                                                                                          |
    | *Inbound packet delay*  | packetDelay                 | _*0*_ , <number> , <probability distribution profile created with probabilityDistributionCreate> |
    | *Inbound packet loss*   | dropRate                    | _*0*_ , <number> , <probability distribution profile created with probabilityDistributionCreate> |
    |                         | enableDropBurst             | _*false*_ , _true_                                                                               |
    |                         | dropBurstSizeFrom           | <number> , *empty*                                                                               |
    |                         | dropBurstSizeTo             | <number> , *empty*                                                                               |
    |                         | limitBursts                 | <number> , *empty*                                                                               |
    """
    # we accept dictionaries only
    paramDict = {} if type(paramDict) is not dict else paramDict

    defaultDict = {
      'packetDelay':        '0',      # int or propability distribution profile, delay  in ms
      'dropRate':           '0',      # int. Indicates the percentage of packets to drop.
      'enableDropBurst':    'false',  # true, false
      'dropBurstSizeFrom':  '',       # int
      'dropBurstSizeTo':    '',       # int
      'limitBursts':        '',       # int
    }

    paramDict = self._getDefaultParams(paramDict, defaultDict)

    # create perl command
    cmd  = '$Tg->Add(diversifEye::NetworkCharacteristics->new('
    cmd += ' name=>"%s",'                                     % name
    cmd += ' network_chars_in_pkt_delay=>"%s",'               % paramDict['packetDelay']
    cmd += ' network_chars_in_drop_rate=>"%s",'               % paramDict['dropRate']
    cmd += ' enableDropBurst=>"%s",'                          % paramDict['enableDropBurst']
    cmd += ' network_chars_in_from_drop_burst_rate=>"%s",'    % paramDict['dropBurstSizeFrom']
    cmd += ' network_chars_in_to_drop_burst_rate=>"%s",'      % paramDict['dropBurstSizeTo']
    cmd += ' network_chars_in_limit_bursts=>"%s",'            % paramDict['limitBursts']
    cmd += '));'

    self._write(cmd)

  def bandwidthRateLimitCreate(self, name, paramDict=None):
    """
    Creates a bandwidth rate limit profile. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked *bold*):

    | *Group*       | *Key*                       | *Value*               |
    | *General*     | rateLimit                   | _*1000*_ , <number>   |
    |               | rateLimitMetric             | _*kbit/s*_ , _mbit/s_ |
    | *Ramping*     | isRampingEnabled            | _*false*_ , _true_    |
    |               | rampingStartFrom            | _*false*_ , _true_    |
    |               | rampingStartFromMetric      | _*kbit/s*_ , _mbit/s_ |
    |               | rampingPeriod               | <number> , *empty*    |
    |               | rampingPeriodMetric         | _*secs*_ , _mins_     |
    """
    # we accept dictionaries only
    paramDict = {} if type(paramDict) is not dict else paramDict

    defaultDict = {
      'rateLimit':              '1000',   # int
      'rateLimitMetric':        'kbit/s', # kbit/s, mbit/s
      'isRampingEnabled':       'false',  # true, false
      'rampingStartFrom':       '10',     # int
      'rampingStartFromMetric': 'kbit/s', # kbit/s, mbit/s
      'rampingPeriod':          '100',    # int
      'rampingPeriodMetric':    'secs',   # secs, mins
    }

    paramDict = self._getDefaultParams(paramDict, defaultDict)

    speedMetricDict = {'kbit/s': 'kbit/s', 'mbit/s': 'Mbit/s' }
    timeMetricDict  = {'secs':   'Secs',   'mins':   'Minutes' }

    paramDict['rateLimitMetric']        = self._getValueFromDict(paramDict['rateLimitMetric'],        speedMetricDict, strict=True)
    paramDict['rampingStartFromMetric'] = self._getValueFromDict(paramDict['rampingStartFromMetric'], speedMetricDict, strict=True)
    paramDict['rampingPeriodMetric']    = self._getValueFromDict(paramDict['rampingPeriodMetric'],    timeMetricDict,  strict=True)

    # create perl command
    cmd  = '$Tg->Add(diversifEye::BandwidthRateLimit->new('
    cmd += ' name=>"%s",'                           % name
    cmd += ' rate_limit=>"%s",'                     % paramDict['rateLimit']
    cmd += ' rate_limit_metric=>"%s",'              % paramDict['rateLimitMetric']
    cmd += ' is_ramping_enabled=>"%s",'             % paramDict['isRampingEnabled']
    cmd += ' start_from_rate_limit=>"%s",'          % paramDict['rampingStartFrom']
    cmd += ' start_from_rate_limit_metric=>"%s",'   % paramDict['rampingStartFromMetric']
    cmd += ' ramp_period=>"%s",'                    % paramDict['rampingPeriod']
    cmd += ' ramp_period_metric=>"%s",'             % paramDict['rampingPeriodMetric']
    cmd += '));'

    self._write(cmd)

  def probabilityDistributionCreate(self, name, *profileDistributionFunctionList, **kwargs):
    """
    Creates a propability distribution profile (GUI: Test group > configuration > profile). profileDistributionFunctionList is a list of percentage:value tuples,
    where value may be a single value or a range. Total percentage must be 100.

    Example:
    | propabilityDistributionCreate | myProfile | 20:1-5 | 30:10 | 50:20 |                          |
    | propabilityDistributionCreate | myProfile | 20:1-5 | 30:10 | 50:20 | descripion=myDescription |
    """

    # create perl command
    cmd  = '$Tg->Add(diversifEye::Profile->new('
    cmd += ' name=>"%s",'                             % name
    cmd += ' description=>"%s",'                      % kwargs['description'] if 'description' in kwargs.keys() else ''
    cmd += ' type=>"Prob. Dist. Func.",'
    cmd += ' profile_distribution_function=>"%s",'    % '/'.join(map(lambda x: ':.'.join(x.split(':')[::-1]), profileDistributionFunctionList))
    cmd += '));'

    self._write(cmd)

  def aggregateGroupCreate(self, name, paramDict=None):
    """
    | paramDict = {
    |   'description':         '',       # string
    |   'enhancedLeaveStats':  'false',  # true, false
    |   'connectionStats':     'false',  # true, false
    |   'extendedTcpStats':    'false',  # true, false
    |   'latencyStats':        'false',  # true, false
    |   'responseCodeStats':   'false',  # true, false
    |   'dhcpStats':           'false',  # true, false
    |   'pppoeStats':          'false',  # true, false
    |   'rtpStats':            'false',  # true, false
    |   'udpStats':            'false',  # true, false
    |   'aggregates':          [],       # list of dicts with this form:, if an aggregate is defined, all 3 keys must be given
    |                                    # {
    |                                    #   'type':               AllClient, AllServer, CiscoAnyConnectVpnClient,
    |                                    #                         CiscoAnyConnectVpnIkeClient, DdosAttacker, DdosListener,
    |                                    #                         DnsClient, FtpClient, FtpServer, Host, HttpClient, HttpServer,
    |                                    #                         MulticastClient, MulticastFileMp2tsServer, MulticastFileServer,
    |                                    #                         MulticastLatencyClient, MulticastLatencyServer, MulticastMp2tsClient,
    |                                    #                         MulticastMp2tsServer, MulticastServer, P2P, P2pReplay, PopClient,
    |                                    #                         PopServer, PortReplay, RtpMulticast, RtpMulticastMp2ts, RtpUnicast,
    |                                    #                         RtpUnicastMp2ts, RtspClient, RtspMp2tsClient, RtspServer, SmtpReceiver,
    |                                    #                         SmtpTransmitter, TcpReplayClient, TcpReplayServer, TelepresenceEndpoint,
    |                                    #                         TwampClient, TwampServer, UnicastLatencyClient, UnicastLatencyServer,
    |                                    #                         VoipUA, VoipUAS
    |                                    #   'normalStats':        true, false
    |                                    #   'fineStats':          true, false
    |                                    # }
    | }
    """
    # we accept dictionaries only
    paramDict = {} if type(paramDict) is not dict else paramDict

    defaultDict = {
      'description':         '',       # string
      'enhancedLeaveStats':  'false',  # true, false
      'connectionStats':     'false',  # true, false
      'extendedTcpStats':    'false',  # true, false
      'latencyStats':        'false',  # true, false
      'responseCodeStats':   'false',  # true, false
      'dhcpStats':           'false',  # true, false
      'pppoeStats':          'false',  # true, false
      'rtpStats':            'false',  # true, false
      'udpStats':            'false',  # true, false
      'aggregates':          [],       # list of dicts with this form:, if an aggregate is defined, all 3 keys must be given
                                       # {
                                       #   'type':               AllClient, AllServer, CiscoAnyConnectVpnClient,
                                       #                         CiscoAnyConnectVpnIkeClient, DdosAttacker, DdosListener,
                                       #                         DnsClient, FtpClient, FtpServer, Host, HttpClient, HttpServer,
                                       #                         MulticastClient, MulticastFileMp2tsServer, MulticastFileServer,
                                       #                         MulticastLatencyClient, MulticastLatencyServer, MulticastMp2tsClient,
                                       #                         MulticastMp2tsServer, MulticastServer, P2P, P2pReplay, PopClient,
                                       #                         PopServer, PortReplay, RtpMulticast, RtpMulticastMp2ts, RtpUnicast,
                                       #                         RtpUnicastMp2ts, RtspClient, RtspMp2tsClient, RtspServer, SmtpReceiver,
                                       #                         SmtpTransmitter, TcpReplayClient, TcpReplayServer, TelepresenceEndpoint,
                                       #                         TwampClient, TwampServer, UnicastLatencyClient, UnicastLatencyServer,
                                       #                         VoipUA, VoipUAS
                                       #   'normalStats':        true, false
                                       #   'fineStats':          true, false
                                       # }
    }

    paramDict = self._getDefaultParams(paramDict, defaultDict)

    # create perl command
    cmd  = '$Tg->Add(diversifEye::AggregateGroup->new('
    cmd += ' name=>"%s",'                                 % name
    cmd += ' description=>"%s",'                          % paramDict['description']
    cmd += ' enhanced_leave_statistics_enabled=>"%s",'    % paramDict['enhancedLeaveStats']
    cmd += ' connection_statistics_enabled=>"%s",'        % paramDict['connectionStats']
    cmd += ' extended_tcp_statistics_enabled=>"%s",'      % paramDict['extendedTcpStats']
    cmd += ' latency_statistics_enabled=>"%s",'           % paramDict['latencyStats']
    cmd += ' response_code_statistics_enabled=>"%s",'     % paramDict['responseCodeStats']
    cmd += ' dhcp_statistics_enabled=>"%s",'              % paramDict['dhcpStats']
    cmd += ' pppoe_statistics_enabled=>"%s",'             % paramDict['pppoeStats']
    cmd += ' rtp_statistics_enabled=>"%s",'               % paramDict['rtpStats']
    cmd += ' udp_statistics_enabled=>"%s",'               % paramDict['udpStats']
    cmd += ')'

    for aggregate in paramDict['aggregates']:
      cmd += '->Add(diversifEye::Aggregate->new('
      cmd += ' type=>"%s",'                         % aggregate['type']
      cmd += ' is_normal_stats_enabled=>"%s",'      % aggregate['normalStats']
      cmd += ' is_fine_stats_enabled=>"%s"'         % aggregate['fineStats']
      cmd += '))'

    cmd += ');'

    self._write(cmd)

  ### tvm-c cli stuff

  def testGroupStart(self, tgName):
    """
    Starts a test group on the controller.
    - tgName: name of test group to be started
    """
    self._execSshCommand('cli -u %s startTestGroup "//%s"' % (self._tvmcUser, tgName))

  def testGroupStop(self, tgName):
    """
    Stops a test group on the controller.
    - tgName: name of test group to be stopped
    """
    self._execSshCommand('cli -u %s stopTestGroup "//%s"' % (self._tvmcUser, tgName))

  def testGroupDelete(self, tgName='all'):
    """
    Deletes a test group on the controller.
    - tgName: name of test group to be delete, if 'all' all test groups will be deleted.
    """
    if tgName != 'all':
      try:
        self.testGroupStop(tgName)
      except:
        pass
      self._execSshCommand('cli -u %s deleteTestGroup "//%s"' % (self._tvmcUser, tgName))
    else:
      for tgName in self.testGroupStatusGet().keys():
        self.testGroupDelete(tgName)
    return True

  def testGroupStatusGet(self):
    """
    Returns a dictionary containing the test groups as key and 'running' or 'stopped' as value.
    """
    output = self._execSshCommand('cli -u %s listTestGroups' % self._tvmcUser)

    tgDict = {}

    for line in output.splitlines():
      if not line.startswith('//'):
        continue

      tgName = line[2:].replace('<<<Running>>>', '').replace('<<<Last>>>', '').rstrip()

      if tgName.endswith('/') or tgName == '':
        continue

      if '<<<Running>>>' in line:
        tgDict[tgName] = 'running'
      else:
        tgDict[tgName] = 'stopped'

    return tgDict

  def cardLevelConfigurationCreate(self, card, paramDict=None):
    """
    Creates a card level configuration for the given _card_. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):
    If instead of _card_ (e.g. 3/1), an interface name (3/1/1) is given, _card_ will be calculated automatically.

    | *Group*             | *Key*                         | *Value*                                                                 |
    | *General*           | description                   | <string> , *empty*                                                      |
    | *TCP*               | tcpRetransmitTimer            | _300_ , _400_ , _*500*_ , _600_ , _700_ , _800_ , _900_ , _1000_ (ms)   |
    |                     | tcpConnectionLimit            | <number [ >0 ]> , *empty*                                               |
    |                     | tcpConnectionInterval         | _*1*_ , _5_ , _10_ , _20_ , _30_ , _60_ (secs)                          |
    |                     | tcpRampUpPeriod               | _*1*_ , _5_ , _10_ , _20_ , _30_ , _60_ (secs)                          |
    |                     | tcpProfile                    | <tcp characteristics profile> , *empty*                                 |
    | *Hosts*             | hostStartupRateLimit          | <number [ 1 .. 10000 ]> , *empty*                                       |
    |                     | hostExplicitRoutes            | _*false*_ , _true_                                                      |
    |                     | hostMaxMtu                    | <number [ *1500* .. 9216 ]>                                             |
    | *TTL*               | tcpTtl                        | <number [ 1 .. *255* ]>                                                 |
    |                     | udpTtl                        | <number [ 1 .. *255* ]>                                                 |
    |                     | igmpTtl                       | <number [ *1* .. 255 ]>                                                 |
    |                     | icmpTtl                       | <number [ 1 .. *255* ]>                                                 |
    | *IGMP/MLD*          | mcEnableUnsolicitedReport     | _*false*_ , _true_                                                      |
    |                     | mcUnsolicitedReportInterval   | <number [ *1* .. 3600000 ]> , <probability distribution profile created with probabilityDistributionCreate> |
    |                     | mcMultipleGroupReports        | _*false*_ , _true_                                                      |
    | *VOIP*              | voipCallAttemptsRateLimit     | <voipCallAttemptsRateLimitParam dictionary> (see below)                 |
    |                     | imsModeEnabled                | _*false*_ , _true_                                                      |
    |                     | imsModeMethod                 | _*dynamic*_ , _preAssigned_                                             |
    | *Miscellaneous*     | dhcpDiscoverSetBroadcastFlag  | _*false*_ , _true_                                                      |
    |                     | dhcpRequestSetBroadcastFlag   | _*false*_ , _true_                                                      |
    |                     | outerVlanProtocolTag          | <2-byte hex value [ 0000 .. FFFF ]> , _*8100*_                          |

    voipCallAttemptsRateLimitParam dictionary:
    | *Key*               | *Value*                   |
    | mode                | _*None*_ , _CPS_ , _BHCA_ |
    | limit               | _*1*_ , <number [ >0 ]>   |
    | rampUpEnabled       | _*false*_ , _true_        |
    | rampUpInitialValue  | _*1*_ , <number [ >0 ]>   |
    | rampUpPeriod        | _*1*_ , <number [ >=0 ]>  |
    | rampUpPeriodMetric  | _secs_ , _*mins*_         |
    """
    card      = '/'.join(card.split('/')[:2])
    paramDict = {} if type(paramDict) is not dict else paramDict

    defaultParamDict = {
        'description'                   : '',
        'tcpRetransmitTimer'            : '500',
        'tcpConnectionLimit'            : '',
        'tcpConnectionInterval'         : '1',
        'tcpRampUpPeriod'               : '1',
        'tcpProfile'                    : '',
        'hostStartupRateLimit'          : '',
        'hostExplicitRoutes'            : 'false',
        'hostMaxMtu'                    : '1500',
        'tcpTtl'                        : '255',
        'udpTtl'                        : '255',
        'igmpTtl'                       : '1',
        'icmpTtl'                       : '255',
        'mcEnableUnsolicitedReport'     : 'false',
        'mcUnsolicitedReportInterval'   : '1',
        'mcMultipleGroupReports'        : 'false',
        'voipCallAttemptsRateLimit'     : {},         #defined below
        'imsModeEnabled'                : 'false',
        'imsModeMethod'                 : 'dynamic',
        'dhcpDiscoverSetBroadcastFlag'  : 'false',
        'dhcpRequestSetBroadcastFlag'   : 'false',
        'outerVlanProtocolTag'          : '8100'
    }

    defaultVoipCallAttemptsDict = {
        'mode'                : 'None',
        'limit'               : '1',
        'rampUpEnabled'       : 'false',
        'rampUpInitialValue'  : '1',
        'rampUpPeriod'        : '1',
        'rampUpPeriodMetric'  : 'mins'
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)
    paramDict['voipCallAttemptsRateLimit'] = self._getDefaultParams(paramDict['voipCallAttemptsRateLimit'], defaultVoipCallAttemptsDict)

    paramDict['tcpConnectionInterval']                            = '1 Sec'                               if paramDict['tcpConnectionInterval'] == '1'                              else "%s Secs" % paramDict['tcpConnectionInterval']
    paramDict['tcpRampUpPeriod']                                  = '1 Sec'                               if paramDict['tcpRampUpPeriod']       == '1'                              else "%s Secs" % paramDict['tcpRampUpPeriod']
    paramDict['voipCallAttemptsRateLimit']['rampUpPeriodMetric']  = 'minutes'                             if paramDict['voipCallAttemptsRateLimit']['rampUpPeriodMetric'] == 'mins' else 'secs'
    paramDict['imsModeMethod']                                    = 'Pre-Assigned Media Path Reservation' if paramDict['imsModeMethod'] == 'preAssigned'                            else 'Dynamic Media Path Reservation'

    cmd  = '$Tg->Add(diversifEye::CardLevelConfig->new('
    cmd += ' name=>"%s", '                                                 % card
    cmd += ' description=>"%s", '                                          % paramDict['description']
    cmd += ' card_level_configuration_retransmit_timer=>"%s", '            % paramDict['tcpRetransmitTimer']
    cmd += ' card_level_configuration_connection_limit=>"%s", '            % paramDict['tcpConnectionLimit']
    cmd += ' card_level_configuration_connection_interval=>"%s", '         % paramDict['tcpConnectionInterval']
    cmd += ' card_level_configuration_ramp_up=>"%s", '                     % paramDict['tcpRampUpPeriod']
    cmd += ' card_level_configuration_tcp_profile=>"%s", '                 % paramDict['tcpProfile']
    cmd += ' host_startup_rate_limit=>"%s", '                              % paramDict['hostStartupRateLimit']
    cmd += ' card_level_configuration_explicit_routes=>"%s", '             % paramDict['hostExplicitRoutes']
    cmd += ' card_level_configuration_max_mtu=>"%s", '                     % paramDict['hostMaxMtu']
    cmd += ' tcp_ttl=>"%s", '                                              % paramDict['tcpTtl']
    cmd += ' udp_ttl=>"%s", '                                              % paramDict['udpTtl']
    cmd += ' igmp_ttl=>"%s", '                                             % paramDict['igmpTtl']
    cmd += ' icmp_ttl=>"%s", '                                             % paramDict['icmpTtl']
    cmd += ' enable_unsolicited_membership_report=>"%s", '                 % paramDict['mcEnableUnsolicitedReport']
    cmd += ' unsolicited_membership_report_interval=>"%s", '               % paramDict['mcUnsolicitedReportInterval']
    cmd += ' enable_multiple_group_reports_per_report=>"%s", '             % paramDict['mcMultipleGroupReports']
    cmd += ' voip_call_attempts_rate_limit_mode=>"%s", '                   % paramDict['voipCallAttemptsRateLimit']['mode']
    cmd += ' voip_call_attempts_rate_limit=>"%s", '                        % paramDict['voipCallAttemptsRateLimit']['limit']
    cmd += ' voip_call_attempts_rate_limit_ramp_up_enabled=>"%s", '        % paramDict['voipCallAttemptsRateLimit']['rampUpEnabled']
    cmd += ' voip_call_attempts_rate_limit_ramp_up_initial_value=>"%s", '  % paramDict['voipCallAttemptsRateLimit']['rampUpInitialValue']
    cmd += ' voip_call_attempts_rate_limit_ramp_up_period=>"%s", '         % paramDict['voipCallAttemptsRateLimit']['rampUpPeriod']
    cmd += ' voip_call_attempts_rate_limit_ramp_up_period_metric=>"%s", '  % paramDict['voipCallAttemptsRateLimit']['rampUpPeriodMetric']
    cmd += ' ims_mode_enabled=>"%s", '                                     % paramDict['imsModeEnabled']
    cmd += ' ims_mode_method=>"%s", '                                      % paramDict['imsModeMethod']
    cmd += ' set_broadcast_bit_in_dhcp_discover=>"%s", '                   % paramDict['dhcpDiscoverSetBroadcastFlag']
    cmd += ' set_broadcast_bit_in_dhcp_request=>"%s", '                    % paramDict['dhcpRequestSetBroadcastFlag']
    cmd += ' outer_vlan_protocol_tag=>"%s"'                                % paramDict['outerVlanProtocolTag']
    cmd += '));'

    self._write(cmd)

  def serviceStateSet(self, tgName, serviceState, elementType, *elementList):
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
        self._execSshCommand('cli -u %s setServiceStateOfHostsInTestGroup "//%s" "%s"' % (self._tvmcUser, tgName, stateDict[serviceState]) )
      else:
        hostList = ','.join(map(lambda x: '"//%s//%s"' % (tgName, x), elementList))
        self._execSshCommand('cli -u %s setServiceStateOfHosts %s "%s"' % (self._tvmcUser, hostList, stateDict[serviceState]) )

    if 'app' in elementType.lower():
      if 'all' in elementList:
        self._execSshCommand('cli -u %s setServiceStateOfApplicationsInTestGroup "//%s" "%s"' % (self._tvmcUser, tgName, stateDict[serviceState]) )
      else:
        appList = ','.join(map(lambda x: '"//%s//%s"' % (tgName, x), elementList))
        self._execSshCommand('cli -u %s setServiceStateOfApplications %s "%s"' % (self._tvmcUser, appList, stateDict[serviceState]) )

  def userSet(self, userName='robot'):
    """
    Sets the user name which will be used to connect to the controller. Default: robot
    """
    self._tvmcUser = userName

  def testGroupCreate(self, tgName, useLowMemoryMode='false'):
    """
    Creates a new test group, discarding all configuration done before (including other test groups).
    No changes at TVM-C are made. Do not use spaces at the beginning and/or end of the test group name.

    - useLowMemoryMode: If true, RAM use by perl is much reduced, but there are some restrictions on
      the order in which certain elements may be added. If false (the default), the restrictions are
      removed, but RAM use can be excessive for large test cases.
    """
    self._tgName = tgName

    lowMemoryDict = {
      'false':  '0',
      'true':   '1'
    }

    #self._tmpFile.close()
    #self._tmpFile = tempfile.NamedTemporaryFile()
    self._initPerlScript(tgName, lowMemoryDict[useLowMemoryMode.lower()])

  def testGroupUpload(self, xmlFile='', tgName=''):
    """
    Uploads the current configuration to the tvm controller. If _xmlFile_ is given, this file will be uploaded instead.
    If _tgName_ is given, the this test group will be uploaded, otherwise the created test group will be uploaded.

    *Note*: An assertion error will be raised if no test group was created prior and no _tgName_ is given.
    """

    if not tgName:
      tgName = self._tgName
    if not tgName:
      raise AssertionError('error: no test group name')

    # upload perl or xml
    if xmlFile:
      if not os.path.isfile(xmlFile):
        raise AssertionError('no such file: %s' % xmlFile)

      self._scpPutFile(xmlFile, '/tmp/robot.xml')
      # TODO: get test group name from xml. try to stop/delete as below
    else:
      self._write('$Tg->End();')
      # copy perl to tvm-c
      self._scpPutFile(self._tmpFile[1], '/tmp/robot.pl')
      # execute remote perl
      self._execSshCommand('perl /tmp/robot.pl > /tmp/robot.xml')
      # try to stop a still running test group
      try:
        self._execSshCommand('cli -u %s stopTestGroup "//%s"' % (self._tvmcUser, tgName))
      except:
        pass
      # try to delete a already existing test group
      try:
        self._execSshCommand('cli -u %s deleteTestGroup "//%s"' % (self._tvmcUser, tgName))
      except:
        pass

    # load test group
    self._execSshCommand('cli -u %s importTestGroup "//" /tmp/robot.xml' % self._tvmcUser)

    # create new empty test group
    self.testGroupCreate(self._tgName)

  def debugFilesGet(self):
    """
    Tries to download the perl and xml file from the TVM-C to the local machine. Default destination directory is the robot output dir.
    If running without robot the users home directory will be used. Returns a dictionary with the location of these files
    """
    returnDict = {}

    try:
      from robot.libraries.BuiltIn import BuiltIn
      debugDir = BuiltIn().replace_variables('${OUTPUTDIR}')
    except:
      debugDir = os.path.expanduser('~')
      pass

    try:
      debugFilePath = debugDir + '/shenick.pl'
      self._scpGetFile('/tmp/robot.pl', debugFilePath)
      returnDict['perlFile'] = debugFilePath
    except:
      pass

    try:
      debugFilePath = debugDir + '/shenick.xml'
      self._scpGetFile('/tmp/robot.xml', debugFilePath)
      returnDict['xmlFile'] = debugFilePath
    except:
      pass

    return returnDict

  def ftpResourceListCreate(self, name, paramDict):
    """
    Creates an FTP resource list for FTP server in Shenick.

    Content of _paramDict_:
    | *Key*         | *Value*                                                                       |
    | description   | <string>                                                                      |
    | resourceList  | <list of ftpResource dictionaries> (see below, at least 1 item is required!). |

    ftpResource dictionary:
    | *Key* | *Value*                                                                                                    |
    | type  | _*fileResource*, fixedSize, rangeResource_                                                                 |
    | path  | <path string>   resource path in FTP application, cannot contain either spaces or single and double quotes |
    | value | <file path to target file> if type is _fileResource_, <file size> if type is _fixedSize_, <probability distribution profile created with probabilityDistributionCreate> if type is _rangeResource_ |
    """
    defaultParamDict = {
      'description':  '',
      'resourceList': []
    }

    typeDict = {
      'fileResource'  : 'File Resource',
      'fixedSize'     : 'Fixed Size',
      'rangeResource' : 'Range Resource'
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    if len(paramDict['resourceList']) == 0:
      raise AssertionError('Error: No ftpResource item found!')

    #create ResourceList
    cmd  = 'my $FtpResourceList_%s = diversifEye::FtpResourceList->new(' % name.replace(' ', '_')
    cmd += ' name=>"%s",'        % name
    cmd += ' description=>"%s"'  % paramDict['description']
    cmd += ');'

    #add Resource items to ResourceList
    for resourceItem in paramDict['resourceList']:
      cmd += '$FtpResourceList_%s->Add(diversifEye::FtpResource->new(' %name.replace(' ', '_')
      cmd += ' type=>"%s",' % typeDict[resourceItem['type']]
      cmd += ' path=>"%s",' % resourceItem['path']
      cmd += ' value=>"%s"' % resourceItem['value']
      cmd += '));'

    #add ResourceList to Test group
    cmd += '$Tg->Add($FtpResourceList_%s);' % name.replace(' ', '_')

    self._write(cmd)

  def ftpCommandListCreate(self, name, paramDict):
    """
    Creates an FTP Commands List for FTP Client in Shenick.

    Content of _paramDict_:
    | *Key*       | *Value*                                       |
    | description | <string>                                      |
    | commandList | <list of ftpCommand dictionaries> (see below) |

    ftpCommand dictionary:
    | *Key* | *Value*                                                                                                    |
    | type  | _ascii_ , _bin_ , _cd_ , _*get*_ , _ls_ , _put_ , _pwd_ , _system_                                         |
    | path  | <path string> (resource path in FTP application, cannot contain either spaces or single and double quotes) |
    """
    defaultParamDict = {
      'description':  '',
      'commandList': []
    }

    defaultCommandsDict = {
      'type' : 'get',
      'path' : ''
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    if len(paramDict['commandList']) == 0:
      raise AssertionError('Error: No ftpCommand item found!')

    #create commandList
    cmd  = 'my $FtpCommandList_%s = diversifEye::FtpCommandList->new(' % name
    cmd += ' name=>"%s",'        % name
    cmd += ' description=>"%s"'  % paramDict['description']
    cmd += ');'

    #add items to commandList
    for commandItem in paramDict['commandList']:
      commandItem = self._getDefaultParams(commandItem, defaultCommandsDict)

      cmd += '$FtpCommandList_%s->Add(diversifEye::FtpCommand->new(' % name
      cmd += ' type=>"%s",' % commandItem['type'].lower()
      cmd += ' path=>"%s"' % commandItem['path']
      cmd += '));'

    #finish commandList
    cmd += '$Tg->Add($FtpCommandList_%s);' % name

    self._write(cmd)

  def ftpExternalServerCreate(self, name, paramDict):
    """
    Creates an external FTP Server in Shenick.

    Content of paramDict (mandatory items are *bold*):

    | *Key*                     | *Value*                                      |
    | description               | <string>                                     |
    | adminState                | _disable_ , _*enable*_                       |
    | host                      | <hostName created with hostCreate> , *empty* |
    | transportPort             | _*21*_ , <udp port>                          |
    | optionalProperties        | [not implemented]                            |
    """
    defaultParam = {
      'description'         : '',
      'adminState'          : 'enable',
      'host'                : '',
      'transportPort'       : '21',
      'optionalProperties'  : ''
    }

    paramDict = self._getDefaultParams(paramDict, defaultParam)

    paramDict['adminState'] = self._getValueFromDict(paramDict['adminState'], {
      'enable':   'Enabled',
      'disable':  'Disabled',
    })

    cmd  = '$Tg->Add(diversifEye::ExternalFtpServer->new('
    cmd += ' name=>"%s",'                 % name
    cmd += ' description=>"%s",'          % paramDict['description']
    cmd += ' administrative_state=>"%s",' % paramDict['adminState']
    cmd += ' host=>"%s",'                 % paramDict['host']
    cmd += ' transport_port=>"%s"'        % paramDict['transportPort']
    cmd += '));'

  def ftpServerCreate(self, name, paramDict):
    """
    Creates an FTP Server in Shenick.

    Content of _paramDict_:
    | *Key*                     | *Value*                                                                                                                   |
    | *host*                    | <hostName> , *empty*                                                                                                      |
    | *resourceList*            | <Ftp resource list name created with ftpResourceListcreate>                                                               |
    | description               | <string> , *empty*                                                                                                        |
    | adminState                | _disable_ , _*enable*_                                                                                                    |
    | scaleFactor               | <number [ >0 ]> , *empty*                                                                                                   |
    | transportPort             | _*21*_ , <udp port>                                                                                                       |
    | dataPorts                 | <udp port> , <probability distribution profile created with probabilityDistributionCreate> , *empty* (use next available) |
    | provisioningMode          | _*singleAppPerRow*_ , _scaledEntity_                                                                                      |
    | normalStats               | _false_ , _*true*_                                                                                                        |
    | fineStats                 | _*false*_ , _true_                                                                                                        |
    | qos                       | <number [ *0* .. 7 ]>                                                                                                     |
    | startAfter                | _*0*_ , <number [ >0 ]> , <probability distribution profile created with probabilityDistributionCreate>                     |
    | startAfterMetric          | _*secs*_ , _ms_ , _mins_                                                                                                  |
    | stopAfter                 | <number [ >0 ]> , <probability distribution profile created with probabilityDistributionCreate>                             |
    | stopAfterMetric           | _*secs*_ , _mins_ , _hours_                                                                                               |
    | aggregateGroup            | <aggregate group created with aggregateGroupCreate> , *empty*                                                             |
    | tcpCharacteristics        | <Tcp characteristics profile created with tcpCharacteristicsCreate> , *empty*                                             |
    | inactivityTimeout         | _*900*_ , <number> , <probability distribution profile created with probabilityDistributionCreate>                        |
    | inactivityTimeoutMetrics  | _*secs*_ , _mins_                                                                                                         |
    """
    defaultParamDict = {
      'description'             : '',
      'adminState'              : 'enable',
      'scaleFactor'             : '',
      'host'                    : '',
      'transportPort'           : '21',
      'dataPorts'               : '',
      'provisioningMode'        : 'singleAppPerRow',
      'normalStats'             : 'true',
      'fineStats'               : 'false',
      'qos'                     : '0',
      'startAfter'              : '0',
      'startAfterMetric'        : 'secs',
      'stopAfter'               : '',
      'stopAfterMetric'         : 'secs',
      'aggregateGroup'          : '',
      'tcpCharacteristics'      : '',
      'resourceList'            : '',
      'inactivityTimeout'       : '900',
      'inactivityTimeoutMetrics': 'secs'
    }

    provisioningModeDict = {
      'singleAppPerRow' : 'Single App per Row',
      'scaledEntity'    : 'Scaled Entity'
    }

    #set missing values to paramDict
    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    paramDict['adminState'] = self._getValueFromDict(paramDict['adminState'], {
      'enable':   'Enabled',
      'disable':  'Disabled',
    })

    cmd  = '$Tg->Add(diversifEye::FtpServer->new('
    cmd += ' name=>"%s",'                      % name
    cmd += ' description=>"%s",'               % paramDict['description']
    cmd += ' administrative_state=>"%s",'      % paramDict['adminState']
    cmd += ' scale_factor=>"%s",'              % paramDict['scaleFactor']
    cmd += ' host=>"%s",'                      % paramDict['host']
    cmd += ' transport_port=>"%s",'            % paramDict['transportPort']
    cmd += ' data_ports=>"%s",'                % paramDict['dataPorts']
    cmd += ' provisioning_mode=>"%s",'         % provisioningModeDict[paramDict['provisioningMode']]
    cmd += ' is_normal_stats_enabled=>"%s",'   % paramDict['normalStats']
    cmd += ' is_fine_stats_enabled=>"%s",'     % paramDict['fineStats']
    cmd += ' qos=>"%s",'                       % paramDict['qos']
    cmd += ' start_after=>"%s",'               % paramDict['startAfter']
    cmd += ' start_after_metric=>"%s",'        % paramDict['startAfterMetric']
    cmd += ' stop_after=>"%s",'                % paramDict['stopAfter']
    cmd += ' stop_after_metric=>"%s",'         % paramDict['stopAfterMetric']
    cmd += ' aggregate_group=>"%s",'           % paramDict['aggregateGroup']
    cmd += ' tcp_characteristics=>"%s",'       % paramDict['tcpCharacteristics']
    cmd += ' file_list=>"%s",'                 % paramDict['resourceList']
    cmd += ' inactivity_timeout=>"%s",'        % paramDict['inactivityTimeout']
    cmd += ' inactivity_timeout_metric=>"%s",' % paramDict['inactivityTimeoutMetrics']
    cmd += '));'

    self._write(cmd)

  def ftpClientCreate(self, name, paramDict):
    """
    Creates an FTP client in Shenick.

    Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked *bold*):
    | *Key*                 | *Value*                                                                                                                   |
    | *commandList*         | <Ftp command list created with ftpCommandListCreate>                                                                      |
    | *host*                | <host created with hostCreate> , *empty*                                                                                  |
    | *server*              | <Ftp server created with ftpServerCreate>                                                                                 |
    | description           | <string> , *empty*                                                                                                        |
    | adminState            | _disable_ , _*enable*_                                                                                                    |
    | serviceState          | _*inService*_ , _outOfService_                                                                                            |
    | scaleFactor           | <number [ >0 ]> , *empty*                                                                                                 |
    | transportPort         | <udp port> , *empty* (use next available)                                                                                 |
    | provisioningMode      | _*singleAppPerRow*_ , _singleClientPerRow_ , _variedAddress_ , _multipleClientsPerRow_ , _scaledEntity_                   |
    | normalStats           | _false_ , _*true*_                                                                                                        |
    | fineStats             | _*false*_ , _true_                                                                                                        |
    | qos                   | <number [ *0* .. 7]>                                                                                                      |
    | startAfter            | _*0*_ , <number [ >0 ]> , <probability distribution profile created with probabilityDistributionCreate>                   |
    | startAfterMetric      | _*secs*_ , _ms_ , _mins_                                                                                                  |
    | stopAfter             | <number [ >0 ]> , <probability distribution profile created with probabilityDistributionCreate> , *empty*                 |
    | stopAfterMetric       | _*secs*_ , _mins_ , _hours_                                                                                               |
    | aggregateGroup        | <aggregate group created with aggregateGroupCreate> , *empty*_                                                            |
    | tcpCharacteristics    | <Tcp characteristics profile created with tcpCharacteristicsCreate> , *empty*                                             |
    | numberOfMultipleApps  | _*2*_ , <number [ >0 ]>                                                                                                   |
    | startIpAddress        | <IP address> , *empty*                                                                                                    |
    | numberIpAddress       | _*2*_ , <number [ >0 ]>                                                                                                   |
    | ipAddressSelection    | _*sequential*_ , _random_ , _zipfian_                                                                                     |
    | zipfianExponent       | _*1.0*_ , <float number [ 0.01 .. 10.0 ]>                                                                                 |
    | connectionRateLimit   | <rate limit profile created with bandwidthRateLimitCreate> , *empty*                                                      |
    | ftpMode               | _active_ , _*passive*_                                                                                                    |
    | dataPorts             | <udp port> , <probability distribution profile created with probabilityDistributionCreate> , *empty* (use next available) |
    | anonymousLoginEnabled | _false_ , _*true*_                                                                                                        |
    | username              | <string> , *empty*                                                                                                        |
    | password              | <string> , *empty*                                                                                                        |
    | commandsDelay         | _*0*_ , <number [ >0 ]> , <probability distribution profile created with probabilityDistributionCreate>                   |
    | commandsDelayMetric   | _*ms*_ , _secs_ , _mins_                                                                                                  |
    | sessionsDelay         | _*0*_ , <number [ >0 ]> , <probability distribution profile created with probabilityDistributionCreate>                   |
    | sessionsDelayMetric   | _*ms*_ , _secs_ , _mins_                                                                                                  |
    """
    defaultParamDict = {
      'description'              : '',
      'adminState'               : 'enable',
      'serviceState'             : 'inService',
      'scaleFactor'              : '',
      'host'                     : '',
      'transportPort'            : '',
      'provisioningMode'         : 'singleAppPerRow',
      'normalStats'              : 'true',
      'fineStats'                : 'false',
      'qos'                      : '0',
      'startAfter'               : '0',
      'startAfterMetric'         : 'secs',
      'stopAfter'                : '',
      'stopAfterMetric'          : 'secs',
      'aggregateGroup'           : '',
      'tcpCharacteristics'       : '',
      'server'                   : '',
      'numberOfMultipleApps'     : '2',
      'startIpAddress'           : '',
      'numberIpAddress'          : '2',
      'ipAddressSelection'       : 'sequential',
      'zipfianExponent'          : '1.0',
      'connectionRateLimit'      : '',
      'ftpMode'                  : 'passive',
      'commandList'              : '',
      'dataPorts'                : '',
      'anonymousLoginEnabled'    : 'true',
      'username'                 : '',
      'password'                 : '',
      'commandsDelay'            : '0',
      'commandsDelayMetric'      : 'ms',
      'sessionsDelay'            : '0',
      'sessionsDelayMetric'      : 'ms'
    }

    serviceStateDict = {
      'inService'     : 'In Service',
      'outOfService'  : 'Out Of Service'
    }

    provisioningModeDict = {
      'singleAppPerRow'       : 'Single App per Row',
      'singleClientPerRow'    : 'Single Client per Row',
      'variedAddress'         : 'Varied Address',
      'multipleClientsPerRow' : 'Multiple Clients per Row',
      'scaledEntity'          : 'Scaled Entity'
    }

    ipAddressSelectionDict = {
      'sequential': 'Sequential',
      'random'    : 'Random',
      'zipfian'   : 'Zipfian Distribution'
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    paramDict['adminState'] = self._getValueFromDict(paramDict['adminState'], {
      'enable':   'Enabled',
      'disable':  'Disabled',
    })

    #build up command
    cmd  = '$Tg->Add(diversifEye::FtpClient->new('
    cmd += ' name=>"%s",'                           % name
    cmd += ' description=>"%s",'                    % paramDict['description']
    cmd += ' administrative_state=>"%s",'           % paramDict['adminState']
    cmd += ' service_state=>"%s",'                  % serviceStateDict[paramDict['serviceState']]
    cmd += ' scale_factor=>"%s",'                   % paramDict['scaleFactor']
    cmd += ' host=>"%s",'                           % paramDict['host']
    cmd += ' transport_port=>"%s",'                 % paramDict['transportPort']
    cmd += ' provisioning_mode=>"%s",'              % provisioningModeDict[paramDict['provisioningMode']]
    cmd += ' is_normal_stats_enabled=>"%s",'        % paramDict['normalStats']
    cmd += ' is_fine_stats_enabled=>"%s",'          % paramDict['fineStats']
    cmd += ' qos=>"%s",'                            % paramDict['qos']
    cmd += ' start_after=>"%s",'                    % paramDict['startAfter']
    cmd += ' start_after_metric=>"%s",'             % paramDict['startAfterMetric']
    cmd += ' stop_after=>"%s",'                     % paramDict['stopAfter']
    cmd += ' stop_after_metric=>"%s",'              % paramDict['stopAfterMetric']
    cmd += ' aggregate_group=>"%s",'                % paramDict['aggregateGroup']
    cmd += ' tcp_characteristics=>"%s",'            % paramDict['tcpCharacteristics']
    cmd += ' server=>"%s",'                         % paramDict['server']
    cmd += ' num_multiple_apps=>"%s",'              % paramDict['numberOfMultipleApps']
    cmd += ' start_ip_address=>"%s",'               % paramDict['startIpAddress']
    cmd += ' num_ip_addresses=>"%s",'               % paramDict['numberIpAddress']
    cmd += ' ip_address_selection_type=>"%s",'      % ipAddressSelectionDict[paramDict['ipAddressSelection']]
    cmd += ' zipfian_exponent=>"%s",'               % paramDict['zipfianExponent']
    cmd += ' connection_rate_limit=>"%s",'          % paramDict['connectionRateLimit']
    cmd += ' ftp_mode=>"%s",'                       % paramDict['ftpMode'].capitalize()
    cmd += ' command_list=>"%s",'                   % paramDict['commandList']
    cmd += ' data_ports=>"%s",'                     % paramDict['dataPorts']
    cmd += ' is_anonymous_enabled=>"%s",'           % paramDict['anonymousLoginEnabled']
    cmd += ' username=>"%s",'                       % paramDict['username']
    cmd += ' password=>"%s",'                       % paramDict['password']
    cmd += ' delay_between_commands=>"%s",'         % paramDict['commandsDelay']
    cmd += ' delay_between_commands_metric=>"%s",'  % paramDict['commandsDelayMetric']
    cmd += ' delay_between_sessions=>"%s",'         % paramDict['sessionsDelay']
    cmd += ' delay_between_sessions_metric=>"%s"'   % paramDict['sessionsDelayMetric']
    cmd += '));'

    self._write(cmd)

  def httpBodyPartListCreate(self, name, *bodyPartList):
    """
    Creates a HTTP Body Part List on Shenick.

    _bodyPartList_ is a list of dictionaries with below keys:
    | *Key*                   | *Value*                                                                       |
    | bodyDataType            | _*file*_ , _text_                                                             |
    | content                 | <string> , *empty*                                                            |
    | clientFilename          | <string> , *empty*                                                            |
    | contentType             | *empty*, _application/activemessage_ , _application/andrew-inset_ , _application/annodex_ , _application/applefile_ , _application/atom+xml_ , _application/atomcat+xml_ , _application/atomicmail_ , _application/atomserv+xml_ , _application/batch-SMTP_ , _application/bbolin_ , _application/beep+xml_ , _application/cals-1840_ , _application/cap_ , _application/commonground_ |
    | contentTransferEnc      | _*notSpecified*_ , _7bit_ , _8bit_ , _binary_ , _base64_ , _quoted-printable_ |
    | contentDispositionList  | _*not supported*_                                                             |
    | additionalHeaders       | <Http header field list created with httpHeaderFieldListCreate>               |
    """
    if len(bodyPartList) == 0: raise AssertionError('No BodyPartItems given!')

    defaultBodyPart = {
      'bodyDataType'            : 'file',
      'content'                 : '',
      'clientFilename'          : '',
      'contentType'             : '',
      'contentTransferEnc'      : 'notSpecified',
      'contentDispositionList'  : '',
      'additionalHeaders'       : ''
    }

    #create BodyPartList
    cmd  = 'my $Bpl_%s = diversifEye::BodyPartList->new();' % name

    #add BodyPart items to BodyPartList
    for part in bodyPartList:
      part = self._getDefaultParams(part, defaultBodyPart)

      cmd += '$Bpl_%s->Add(diversifEye::BodyPart->new(' % name
      cmd += ' body_data_type=>"%s",'           %  part['bodyDataType'].capitalize()
      cmd += ' content=>"%s",'                  %  part['content']
      cmd += ' client_file_name=>"%s",'         %  part['clientFilename']
      cmd += ' content_type=>"%s",'             %  part['contentType']
      cmd += ' content_transfer_end=>"%s", '    % ('Not specified' if part['contentTransferEnc'] == 'notSpecified' else part['contentTransferEnc'])
      cmd += ' content_disposition_list=>"%s",' %  part['contentDispositionList']
      cmd += ' additional_headers=>"%s"'        %  part['additionalHeaders']
      cmd += '));'

    self._write(cmd)

  def httpResourceListCreate(self, name, paramDict):
    """
    Creates an HTTP server resource list on Shenick.

    Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):
    | *Key*          | *Value*                                         |
    | description    | <string> , *empty*                              |
    | *resourceList* | <list of httpResource dictionaries> (see below) |

    httpResource dictionary:
    | *Key* | *Value*                                                                                                                                                  |
    | type  | _*fileResource*_ , _randomData_                                                                                                                          |
    | path  | <path string>                                                                                                                                            |
    | value | <file path> (if type is 'fileResource') , <size> , <probability distribution profile created with probabilityDistributionCreate> if type is _randomData_ |
    """
    defaultParamDict = {
      'description':  '',
      'resourceList': []
    }

    typeDict = {
      'fileResource': 'File Resource',
      'randomData':   'Random Data',
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    if len(paramDict['resourceList']) == 0:
      raise AssertionError('Error: No httpResource item found!')

    #create ResourceList
    cmd  = 'my $HttpResourceList_%s = diversifEye::HttpResourceList->new(' % name
    cmd += ' name=>"%s",'        % name
    cmd += ' description=>"%s"'  % paramDict['description']
    cmd += ');'

    #add Resource items to ResourceList
    for resourceItem in paramDict['resourceList']:
      cmd += '$HttpResourceList_%s->Add(diversifEye::HttpResource->new(' %name
      cmd += ' type=>"%s",' % typeDict[resourceItem['type']]
      cmd += ' path=>"%s",' % resourceItem['path']
      cmd += ' value=>"%s"' % resourceItem['value']
      cmd += '));'

    #add ResourceList to Test group
    cmd += '$Tg->Add($HttpResourceList_%s);' % name

    self._write(cmd)

  def httpHeaderFieldListCreate(self, name, paramDict):
    """
    Creates an HTTP header field list on Shenick.

    Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):
    | *Key*             | *Value*                                |
    | description       | <string> , *empty*                     |
    | *headerFieldList* | <list of httpHeaderField dictionaries> |

    HttpHeaderField dictionary:
    | *Key*     | *Value*            |
    | fieldName | *empty* , _Host_ , _User-Agent_ , _Accept_ , _Accept-Encondig_ , _Accept-Language_ , _Accept-Charset_ , _Keep-Alive_ , _Connection_ , _Authorization_ , _Referer_ , _Cookie_ , _Content-Length_ , _Content-Type_ , <other valid header name> |
    | fieldBody | <string> , *empty* |
    """
    defaultParam = {
      'description'     : '',
      'headerFieldList' : []
    }

    defaultHeaderField = {
      'fieldName' : '',
      'fieldBody' : ''
    }

    paramDict = self._getDefaultParams(paramDict, defaultParam)

    if len(paramDict['headerFieldList']) == 0:
      raise AssertionError("Error: 'headerFieldList' entry in paramDict must not be empty!")

    cmd  = 'my $Hhfl_%s = diversifEye::HttpHeaderFieldList->new(' % name
    cmd += ' name=>"%s",'       % name
    cmd += ' description=>"%s"' % paramDict['description']
    cmd += ');'

    for headerField in paramDict['headerFieldList']:
      headerField = self._getDefaultParams(headerField, defaultHeaderField)

      cmd += '$Hhfl_%s->Add(diversifEye::HttpHeaderField->new(' % name
      cmd += ' field_name=>"%s",' % headerField['fieldName']
      cmd += ' field_body=>"%s"'  % headerField['fieldBody']
      cmd += '));'

    cmd += '$Tg->Add($Hhfl_%s);' % name

    self._write(cmd)

  def httpRequestListCreate(self, name, paramDict):
    """
    Creates an HTTP request list on Shenick.

    Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):
    | *Key*           | *Value*                                   |
    | description     | <string> , *empty*                        |
    | selectionMode   | _*sequential*_ , _random_ , _zipfian_     |
    | zipfianExponent | _*1.0*_, <float number [ 0.01 ..  10.0 ]> |
    | *requestList*   | <list of httpRequestField dictionaries>   |

    httpRequestField dictionary:
    | *Key*               | *Value*                                                         |
    | method              | _*GET*_ , _HEAD_ , _POST_                                       |
    | uri                 | <Uri string> (path to file on http server)                      |
    | headerFieldList     | <Http header field list created with httpHeaderFieldListCreate> |
    | *following values are only applicable if _method_ is set to _POST_ :*               |
    | contentType         | _*application/x-www-form-urlencoded*_ , _multipart/form-data_   |
    | contentTypeCharset  | *empty*_ , _ascii_ , _big5_ , _bs_4730_ , _euc-jp_ , _euc-kr_ , _gb2312_ , _gbk_ , _iso-2022-cn_ , _iso-2022-cn-ext_ , _iso-2022-jp_ , _iso-2022-jp-2_ , _iso-2022-kr_ , _iso-8859-1_ , _iso-8859-2_ , _iso-8859-3_ , _iso-8859-4_ , _iso-8859-5_ , _iso-8859-6_ , _iso-8859-7_ , _iso-8859-8_ , _iso-8859-9_ , _iso-8859-10_ , _iso-8859-13_ , _iso-8859-14_ , _iso-8859-15_ , _iso-8859-16_ , _koi8-r_ , _koi8-u_ , _korean_ , _latin1_ , _none_ , _null_ , _shift_jis_ , _tis-620_ , _windows-1250_ , _windows-1251_ , _windows-1252_ , _windows-1253_ , _windows-1254_ , _windows-1255_ , _windows-1256_ , _windows-1257_ , _windows-1258_ , _windows-31j_ , _windows-936_ , _us-ascii_ , _utf-7_ , _utf-8_ , _utf-16_ , _utf-32_ , <other valid charset name> |
    | content             | <string> , *empty*                                              |
    | bodyPartList        | *empty*                                                         |
    """
    defaultParamDict = {
      'description':      '',
      'selectionMode':    'Sequential',
      'zipfianExponent':  '1',
      'requestList':      []
    }

    defaultRequestDict = {
      'method' :            'get',
      'uri':                '',
      'headerFieldList':    '',
      'contentType':        'application/x-www-form-urlencoded',
      'contentTypeCharset': '',
      'content':            '',
      'bodyPartList':       ''
    }

    selectionModeDict = {
      'sequential'  : 'Sequential',
      'random'      : 'Random',
      'zipfian'     : 'Zipfian Distribution'
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    if len(paramDict['requestList']) == 0:
      raise AssertionError('Error: No httpRequest item found!')

    #create commandList
    cmd  = 'my $HttpRequestList_%s = diversifEye::HttpRequestList->new(' % name
    cmd += ' name=>"%s",'              % name
    cmd += ' description=>"%s",'       % paramDict['description']
    cmd += ' selection_mode=>"%s",'    % selectionModeDict[paramDict['selectionMode'].lower()]
    cmd += ' zipfian_exponent=>"%s",'  % paramDict['zipfianExponent']
    cmd += ');'

    #add items to commandList
    for requestItem in paramDict['requestList']:
      requestItem = self._getDefaultParams(requestItem, defaultRequestDict)

      cmd += '$HttpRequestList_%s->Add(diversifEye::HttpRequest->new(' % name
      cmd += ' method=>"%s",'                % requestItem['method'].upper()
      cmd += ' uri=>"%s",'                   % requestItem['uri']
      cmd += ' header_field_list=>"%s",'     % requestItem['headerFieldList']
      cmd += ' content_type=>"%s",'          % requestItem['contentType']
      cmd += ' content_type_charset=>"%s",'  % requestItem['contentTypeCharset']
      cmd += ' content=>"%s",'               % requestItem['content']
      cmd += ' body_part_list=>"%s",'        % requestItem['bodyPartList']
      cmd += '));'

    #finish commandList
    cmd += '$Tg->Add($HttpRequestList_%s);' % name

    self._write(cmd)

  def httpExternalProxyCreate(self, name, paramDict):
    """
    Creates an external HTTP proxy server on Shenick.

    Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):
    | *Key*               | *Value*                                                                             |
    | *host*              | <host created with hostCreate> (the host must have been created as 'External Host') |
    | description         | <string> , *empty*                                                                  |
    | adminState          | _disable_ , _*enable*_                                                              |
    | transportPort       | _*8080*, <tcp port>_                                                                |
    | optionalProperties  | _*not supported*_                                                                   |
    """
    defaultParamDict = {
      'host'                     : '',
      'description'              : '',
      'adminState'               : 'enable',
      'transportPort'            : '8080',
      'optionalProperties'       : '',
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    paramDict['adminState'] = self._getValueFromDict(paramDict['adminState'], {
      'enable':   'Enabled',
      'disable':  'Disabled',
    })

    #build up command
    cmd  = '$Tg->Add(diversifEye::ExternalHttpProxy->new('
    cmd += ' name=>"%s",'                           % name
    cmd += ' host=>"%s",'                           % paramDict['host']
    cmd += ' description=>"%s",'                    % paramDict['description']
    cmd += ' administrative_state=>"%s",'           % paramDict['adminState']
    cmd += ' transport_port=>"%s",'                 % paramDict['transportPort']
    cmd += ' optional_properties=>"%s"'             % paramDict['optionalProperties']
    cmd += '));'

    self._write(cmd)

  def httpExternalServerCreate(self, name, paramDict):
    """
    Creates an external HTTP server on Shenick.

    Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):
    | *Key*               | *Value*                                                                             |
    | *host*              | <host created with hostCreate> (the host must have been created as 'External Host') |
    | description         | <string> , *empty*                                                                  |
    | adminState          | _disable_ , _*enable*_                                                              |
    | transportPort       | _*80*, <tcp port>_                                                                  |
    | optionalProperties  | _*not supported*_                                                                   |
    """
    defaultParamDict = {
      'description'              : '',
      'host'                     : '',
      'adminState'               : 'enable',
      'transportPort'            : '80',
      'optionalProperties'       : '',
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    paramDict['adminState'] = self._getValueFromDict(paramDict['adminState'], {
      'enable':   'Enabled',
      'disable':  'Disabled',
    })

    #build up command
    cmd  = '$Tg->Add(diversifEye::ExternalHttpServer->new('
    cmd += ' name=>"%s",'                           % name
    cmd += ' host=>"%s",'                           % paramDict['host']
    cmd += ' description=>"%s",'                    % paramDict['description']
    cmd += ' administrative_state=>"%s",'           % paramDict['adminState']
    cmd += ' transport_port=>"%s",'                 % paramDict['transportPort']
    cmd += ' optional_properties=>"%s"'             % paramDict['optionalProperties']
    cmd += '));'

    self._write(cmd)

  def httpServerCreate(self, name, paramDict):
    """
    Creates an HTTP server on Shenick.

    Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):
    | *Key*                             | *Value*                                                                                                    |
    | *host*                            | <host created with hostCreate>                                                                             |
    | *resourceList*                    | <Http resource list created with httpResourceListCreate>                                                   |
    | description                       | <string> , *empty*                                                                                         |
    | adminState                        | _disable_ , _*enable*_                                                                                     |
    | numberOfServers                   | _*1*_ , <number [>1]>                                                                                      |
    | transportPort                     | _*80*_ , <udp port>                                                                                        |
    | normalStats                       | _false_ , _*true*_                                                                                         |
    | fineStats                         | _*false*_ , _true_                                                                                         |
    | qos                               | <number [ *0* .. 7 ]>                                                                                      |
    | startAfter                        | _*0*_ , <number [ >0 ]> , <probability distribution profile created with probabilityDistributionCreate>    |
    | startAfterMetric                  | _*secs*_ , _ms_ , _mins_                                                                                   |
    | stopAfter                         | <number [ >0 ]> , <probability distribution profile created with probabilityDistributionCreate> , *empty*  |
    | stopAfterMetric                   | _*secs*_ , _mins_ , _hours_                                                                                |
    | aggregateGroup                    | <aggregate group created with aggregateGroupCreate> , *empty*                                              |
    | tcpCharacteristics                | <Tcp characteristics profile created with tcpCharacteristicsCreate> , *empty*                              |
    | extendedSizeBasedRequestsEnabled  | _*false*_ , _true_                                                                                         |
    | tlsEnabled                        | _*false*_ , _true_                                                                                         |
    | responseDelay                     | <number [ >=0 ]> , <probability distribution profile created with probabilityDistributionCreate> , *empty* |
    | responseDelayMetric               | _*ms*_ , _secs_ , _mins_                                                                                   |
    | acwsDomainName                    | <string> , *empty*                                                                                         |
    """
    defaultParam = {
      'host'                              : '',
      'resourceList'                      : '',
      'description'                       : '',
      'adminState'                        : 'enable',
      'numberOfServers'                   : '1',
      'transportPort'                     : '80',
      'normalStats'                       : 'true',
      'fineStats'                         : 'false',
      'qos'                               : '0',
      'startAfter'                        : '0',
      'startAfterMetric'                  : 'secs',
      'stopAfter'                         : '',
      'stopAfterMetric'                   : 'secs',
      'aggregateGroup'                    : '',
      'tcpCharacteristics'                : '',
      'extendedSizeBasedRequestsEnabled'  : 'false',
      'tlsEnabled'                        : 'false',
      'responseDelay'                     : '',
      'responseDelayMetric'               : 'ms',
      'acwsDomainName'                    : '',
    }

    paramDict = self._getDefaultParams(paramDict, defaultParam)

    paramDict['adminState'] = self._getValueFromDict(paramDict['adminState'], {
      'enable':   'Enabled',
      'disable':  'Disabled',
    })

    # add scaleFactor as only this is important
    paramDict['scaleFactor'] = ('' if paramDict['numberOfServers'] == '1' else paramDict['numberOfServers'])

    cmd  = '$Tg->Add(diversifEye::HttpServer->new('
    cmd += ' name=>"%s",'                                 % name
    cmd += ' host=>"%s",'                                 % paramDict['host']
    cmd += ' resource_list=>"%s",'                        % paramDict['resourceList']
    cmd += ' description=>"%s",'                          % paramDict['description']
    cmd += ' administrative_state=>"%s",'                 % paramDict['adminState']
    cmd += ' scale_factor=>"%s",'                         % paramDict['scaleFactor']
    cmd += ' transport_port=>"%s",'                       % paramDict['transportPort']
    cmd += ' is_normal_stats_enabled=>"%s",'              % paramDict['normalStats']
    cmd += ' is_fine_stats_enabled=>"%s",'                % paramDict['fineStats']
    cmd += ' qos=>"%s",'                                  % paramDict['qos']
    cmd += ' start_after=>"%s",'                          % paramDict['startAfter']
    cmd += ' start_after_metric=>"%s",'                   % paramDict['startAfterMetric']
    cmd += ' stop_after=>"%s",'                           % paramDict['stopAfter']
    cmd += ' stop_after_metric=>"%s",'                    % paramDict['stopAfterMetric']
    cmd += ' aggregate_group=>"%s",'                      % paramDict['aggregateGroup']
    cmd += ' tcp_characteristics=>"%s",'                  % paramDict['tcpCharacteristics']
    cmd += ' enable_extended_size_based_requests=>"%s",'  % paramDict['extendedSizeBasedRequestsEnabled']
    cmd += ' enable_tls=>"%s",'                           % paramDict['tlsEnabled']
    cmd += ' response_delay=>"%s",'                       % paramDict['responseDelay']
    cmd += ' response_delay_metric=>"%s",'                % paramDict['responseDelayMetric']
    cmd += ' acws_domain_name=>"%s"'                      % paramDict['acwsDomainName']
    cmd += '));'

    self._write(cmd)

  def httpClientCreate(self, name, paramDict):
    """
    Creates an HTTP Client on Shenick. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):

    | *Group*             | *Key*                             | *Value*                                                                                               |
    | Application details | *host*                            | <host created with hostCreate>                                                            |
    |                     | numberOfClients                   | _*1*_ , <number>                                                                                      |
    |                     | description                       | <string> , *empty*                                                                                      |
    |                     | tlsEnabled                        | _*false*_ , _true_                                                                                       |
    |                     | transportPort                     | <tcp port> , *empty* (use next available)                                                            |
    |                     | qos                               | < *0* .. 7>                                                                                   |
    |                     | tcpCharacteristics                | <Tcp characteristics profile created with tcpCharacteristicsCreate> , *empty*                         |
    |                     | connectionRateLimit               | <rateLimit profile name created with bandwidthRateLimitCreate> , *empty*                              |
    | Client details      | *server*                          | <name of Http server created with httpServerCreate> , *empty*                                         |
    |                     | *requestList*                     | <name of Http request list created with httpRequestListCreate> , *empty*                              |
    |                     | proxy                             | <name of external Http proxy created with httpExternalProxyCreate> , *empty*                          |
    |                     | proxyHeaders                      | *empty*                                                                                                |
    |                     | httpVersion                       | _0.9_ , _*1.1*_ , _1.0_                                                                                     |
    |                     | authenticationUsername            | <string> , *empty*                                                                                      |
    |                     | authenticationPassword            | <string> , *empty*                                                                                      |
    |                     | authenticationUseInitialReq       | _*false*_                                                                                             |
    |                     | keywordSubstitutionEnabled        | _*false*_ , _true_                                                                                       |
    |                     | headerFieldList                   | <name of Http header fields list created with httpHeaderFieldListCreate> , *empty*                   |
    |                     | acwsEnabled                       | _*false*_ , _true_                                                                                       |
    |                     | acwsUsername                      | <string> , *empty*                                                                                      |
    |                     | acwsUsergroup                     | <string> , *empty*                                                                                      |
    |                     | acwsLicenseKey                    | <string> , *empty*                                                                                      |
    |                     | acwsAgentVersion                  | <string> , *empty*                                                                                      |
    | Connections details | requestsPerConnection             | _*1*_ , <number [ >0 ]>                                                                                 |
    |                     | requestDelay                      | _*0*_ , <number [ >=0 ]>                                                                                |
    |                     | requestDelayMetric                | _*ms*_ , _secs_ , _mins_                                                                                    |
    |                     | connectionsDelay                  | _*0*_ , <number [ >=0 ]>                                                                                 |
    |                     | connectionsDelayMetric            | _*ms*_ , _secs_ , _mins_                                                                                    |
    |                     | retrySessionAfterFailure          | _*false*_ , _true_                                                                                       |
    |                     | retrySessionCount                 | _*1*_ , <number [ 1 .. 10 ]>                                                                               |
    |                     | retrySessionDelay                 | _*1*_ , <number [ 1 - 3600 ]> (seconds)                                                                     |
    |                     | retrySessionDelayMetric           | _*secs*_ , _ms_ , _mins_                                                                                    |
    |                     | repeatSessionOnSuccess            | _*false*_ , _true_                                                                                       |
    |                     | repeatSessionCount                | _*1*_ , <number [ 1 - 10 ]>                                                                               |
    |                     | repeatSessionDelay                | _*1*_ , <number [ 1 - 3600 ]> (seconds)                                                                     |
    |                     | repeatSessionDelayMetric          | _*secs*_ , _ms_ , _mins_                                                                                    |
    |                     | ignoreRedirectsEnabled            | _*false*_ , _true_                                                                                       |
    |                     | connectionResetEnabled            | _*false*_ , _true_                                                                                       |
    | Additional details  | normalStats                       | _false_ , _*true*_                                                                                       |
    |                     | fineStats                         | _*false*_ , _true_                                                                                       |
    |                     | httpResponseCodeStats             | _*false*_ , _true_                                                                                       |
    |                     | startAfter                        | _*0*_ , <number [ >0 ]> , <probability distribution profile created with probabilityDistributionCreate> |
    |                     | startAfterMetric                  | _*secs*_ , _ms_ , _mins_                                                                                    |
    |                     | stopAfter                         | <number [ >0]> , <probability distribution profile created with probabilityDistributionCreate> , *empty* |
    |                     | stopAfterMetric                   | _*secs*_ , _mins_ , _hours_                                                                                 |
    |                     | aggregateGroup                    | <aggregate group name created with aggregateGroupCreate> , *empty*                                    |
    """

    # old help for reference

    # Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):
    # | *Key*                             | *Value*                                                                                              |
    # | *host*                            | <host  created with hostCreate>                                                            |
    # | *server*                          | _*''*, <name of Http Server> created with `httpServerCreate`_                                         |
    # | *requestList*                     | _*''*, <name of Http Request list> created with `httpRequestListCreate`_                              |
    # | description                       | <string> , *empty*                                                                                      |
    # | adminState                        | _*enabled*, disabled_                                                                                 |
    # | serviceState                      | _*inService*_ , _outOfService_                                                                           |
    # | numberOfClients                   | _*1*, <integer>_                                                                                      |
    # | transportPort                     | _*''* (use next available), or <tcp port>_                                                            |
    # | provisioningMode                  | _*singleAppPerRow*, singleClientPerRow, variedAddress, multipleClientsPerRow, scaledEntity_           |
    # | normalStats                       | _false_ , _*true*_                                                                                       |
    # | fineStats                         | _*false*_ , _true_                                                                                       |
    # | qos                               | <number [ *0* .. 7 ]>                                                                                   |
    # | startAfter                        | _*0*_ , <number [ >0 ]> , <probability distribution profile created with probabilityDistributionCreate> |
    # | startAfterMetric                  | _*secs*_ , _ms_ , _mins_                                                                                    |
    # | stopAfter                         | _*''*, <integer> > 0, or <probability distribution profile created with probabilityDistributionCreate> created with `probabilityDistributionCreate`_ |
    # | stopAfterMetric                   | _*secs*_ , _mins_ , _hours_                                                                                 |
    # | aggregateGroup                    | <aggregate group created with aggregateGroupCreate> , *empty*                                    |
    # | tcpCharacteristics                | <Tcp characteristics profile created with tcpCharacteristicsCreate> , *empty*                         |
    # | numberOfMultipleApps              | _*2*, <integer> >0_                                                                                   |
    # | startIpAddress                    | <IP address> , *empty*                                                                                  |
    # | numberIpAddress                   | _*2*, <integer> >0_                                                                                   |
    # | ipAddressSelection                | _*sequential*_ , _random_ , _zipfian_                                                                       |
    # | zipfianExponent                   | _*1.0*_ , <float number [ 0.01 .. 10.0 ]>_                                                                     |
    # | connectionRateLimit               | _*''*, <rateLimit profile name> created with `bandwidthRateLimitCreate`_                              |
    # | retrySessionAfterFailure          | _*false*_ , _true_                                                                                       |
    # | retrySessionCount                 | _*1*, <integer> 1 - 10_                                                                               |
    # | retrySessionDelay                 | _*1*, <integer> 1 - 3600 seconds_                                                                     |
    # | retrySessionDelayMetric           | _*secs*_ , _ms_ , _mins_                                                                                    |
    # | repeatSessionOnSuccess            | _*false*_ , _true_                                                                                       |
    # | repeatSessionCount                | _*1*, <integer> 1 - 10_                                                                               |
    # | repeatSessionDelay                | _*1*, <integer> 1 - 3600 seconds_                                                                     |
    # | repeatSessionDelayMetric          | _*secs*_ , _ms_ , _mins_                                                                                    |
    # | proxy                             | _*''*, <name of external http proxy> created with `httpExternalProxyCreate`_                          |
    # | proxyHeaders                      | _*''*_                                                                                                |
    # | httpVersion                       | _*1.1*, 0.9, 1.0_                                                                                     |
    # | tlsEnabled                        | _*false*_ , _true_                                                                                       |
    # | authenticationUsername            | <string> , *empty*                                                                                      |
    # | authenticationPassword            | <string> , *empty*                                                                                      |
    # | authenticationUseInitialReq       | _*false*_                                                                                             |
    # | requestsPerConnection             | _*1*, <integer> >= 1_                                                                                 |
    # | requestDelay                      | _*0*_ , <number [ >=0 ]>                                                                                 |
    # | requestDelayMetric                | _*ms*_ , _secs_ , _mins_                                                                                    |
    # | connectionsDelay                  | _*0*_ , <number [ >=0 ]>                                                                                 |
    # | connectionsDelayMetric            | _*ms*_ , _secs_ , _mins_                                                                                    |
    # | ignoreRedirectsEnabled            | _*false*_ , _true_                                                                                       |
    # | connectionResetEnabled            | _*false*_ , _true_                                                                                       |
    # | resourceList                      | <Http resource list created with httpResourceListCreate>                                     |
    # | httpResponseCodeStats             | _*false*_ , _true_                                                                                       |
    # | keywordSubstitutionEnabled        | _*false*_ , _true_                                                                                       |
    # | headerFieldList                   | <Http header fields list created with httpHeaderFieldListCreate> , *empty*                   |
    # | acwsEnabled                       | _*false*_ , _true_                                                                                       |
    # | acwsUsername                      | <string> , *empty*                                                                                      |
    # | acwsUsergroup                     | <string> , *empty*                                                                                      |
    # | acwsLicenseKey                    | <string> , *empty*                                                                                      |
    # | acwsAgentVersion                  | <string> , *empty*                                                                                      |

    defaultParam = {
      'host'                        : '',
      'server'                      : '',
      'requestList'                 : '',
      'description'                 : '',
      'adminState'                  : 'enable',
      'serviceState'                : 'inService',
      'numberOfClients'             : '1',
      'scaleFactor'                 : '',
      'transportPort'               : '',
      'provisioningMode'            : 'singleAppPerRow',
      'normalStats'                 : 'true',
      'fineStats'                   : 'false',
      'qos'                         : '0',
      'startAfter'                  : '0',
      'startAfterMetric'            : 'secs',
      'stopAfter'                   : '',
      'stopAfterMetric'             : 'secs',
      'aggregateGroup'              : '',
      'tcpCharacteristics'          : '',
      'numberOfMultipleApps'        : '2',
      'startIpAddress'              : '',
      'numberIpAddress'             : '2',
      'ipAddressSelection'          : 'sequential',
      'zipfianExponent'             : '1.0',
      'connectionRateLimit'         : '',
      'retrySessionAfterFailure'    : 'false',
      'retrySessionCount'           : '1',
      'retrySessionDelay'           : '1',
      'retrySessionDelayMetric'     : 'secs',
      'repeatSessionOnSuccess'      : 'false',
      'repeatSessionCount'          : '1',
      'repeatSessionDelay'          : '1',
      'repeatSessionDelayMetric'    : 'secs',
      'proxy'                       : '',
      'proxyHeaders'                : '',
      'httpVersion'                 : '1.1',
      'tlsEnabled'                  : 'false',
      'authenticationUsername'      : '',
      'authenticationPassword'      : '',
      'authenticationUseInitialReq' : 'false',
      'requestsPerConnection'       : '1',
      'requestDelay'                : '0',
      'requestDelayMetric'          : 'ms',
      'connectionsDelay'            : '0',
      'connectionsDelayMetric'      : 'ms',
      'ignoreRedirectsEnabled'      : 'false',
      'connectionResetEnabled'      : 'false',
      'resourceList'                : '',
      'httpResponseCodeStats'       : 'false',
      'keywordSubstitutionEnabled'  : 'false',
      'headerFieldList'             : '',
      'acwsEnabled'                 : 'false',
      'acwsUsername'                : '',
      'acwsUsergroup'               : '',
      'acwsLicenseKey'              : '',
      'acwsAgentVersion'            : '',
    }

    serviceStateDict = {
      'inService'    : 'In Service',
      'outOfService' : 'Out of Service'
    }

    provisioningModeDict = {
      'singleAppPerRow'       : 'Single App per Row',
      'singleClientPerRow'    : 'Single Client per Row',
      'variedAddress'         : 'Varied Address',
      'multipleClientsPerRow' : 'Muliple Clients per Row',
      'scaledEntity'          : 'Scaled Entity'
    }

    ipAddressSelectionTypeDict = {
      'sequential'  : 'Sequential',
      'random'      : 'Random',
      'zipfian'     : 'Zipfian Distribution'
    }

    paramDict = self._getDefaultParams(paramDict, defaultParam)

    paramDict['adminState'] = self._getValueFromDict(paramDict['adminState'], {
      'enable':   'Enabled',
      'disable':  'Disabled',
    })

    if paramDict['provisioningMode'] in ['singleAppPerRow', 'singleClientPerRow'] and paramDict['numberOfClients'] == '1':
      paramDict['scaleFactor'] = ''
    else:
      paramDict['scaleFactor'] = paramDict['numberOfClients']

    cmd  = '$Tg->Add(diversifEye::HttpClient->new('
    cmd += ' name=>"%s",'                                 % name
    cmd += ' host=>"%s",'                                 % paramDict['host']
    cmd += ' server=>"%s",'                               % paramDict['server']
    cmd += ' requested_list=>"%s",'                       % paramDict['requestList']
    cmd += ' description=>"%s",'                          % paramDict['description']
    cmd += ' administrative_state=>"%s",'                 % paramDict['adminState'].capitalize()
    cmd += ' service_state=>"%s",'                        % serviceStateDict[paramDict['serviceState']]
    cmd += ' scale_factor=>"%s",'                         % paramDict['scaleFactor']
    cmd += ' transport_port=>"%s",'                       % paramDict['transportPort']
    cmd += ' provisioning_mode=>"%s",'                    % provisioningModeDict[paramDict['provisioningMode']]
    cmd += ' is_normal_stats_enabled=>"%s",'              % paramDict['normalStats']
    cmd += ' is_fine_stats_enabled=>"%s",'                % paramDict['fineStats']
    cmd += ' qos=>"%s",'                                  % paramDict['qos']
    cmd += ' start_after=>"%s",'                          % paramDict['startAfter']
    cmd += ' start_after_metric=>"%s",'                   % paramDict['startAfterMetric']
    cmd += ' stop_after=>"%s",'                           % paramDict['stopAfter']
    cmd += ' stop_after_metric=>"%s",'                    % paramDict['stopAfterMetric']
    cmd += ' aggregate_group=>"%s",'                      % paramDict['aggregateGroup']
    cmd += ' tcp_characteristics=>"%s",'                  % paramDict['tcpCharacteristics']
    cmd += ' num_multiple_apps=>"%s",'                    % paramDict['numberOfMultipleApps']
    cmd += ' start_ip_address=>"%s",'                     % paramDict['startIpAddress']
    cmd += ' num_ip_addresses=>"%s",'                     % paramDict['numberIpAddress']
    cmd += ' ip_address_selection_type=>"%s",'            % ipAddressSelectionTypeDict[paramDict['ipAddressSelection']]
    cmd += ' zipfian_exponent=>"%s",'                     % paramDict['zipfianExponent']
    cmd += ' connection_rate_limit=>"%s",'                % paramDict['connectionRateLimit']
    cmd += ' retry_session_after_failure=>"%s",'          % paramDict['retrySessionAfterFailure']
    cmd += ' max_number_of_session_retries=>"%s",'        % paramDict['retrySessionCount']
    cmd += ' delay_before_session_retry=>"%s",'           % paramDict['retrySessionDelay']
    cmd += ' delay_before_session_retry_metric=>"%s",'    % paramDict['retrySessionDelayMetric']
    cmd += ' repeat_session_on_success=>"%s",'            % paramDict['repeatSessionOnSuccess']
    cmd += ' repeat_session_count=>"%s",'                 % paramDict['repeatSessionCount']
    cmd += ' delay_before_session_repeat=>"%s",'          % paramDict['repeatSessionDelay']
    cmd += ' delay_before_session_repeat_metric=>"%s",'   % paramDict['repeatSessionDelayMetric']
    cmd += ' proxy=>"%s",'                                % paramDict['proxy']
    cmd += ' proxy_headers=>"%s",'                        % paramDict['proxyHeaders']
    cmd += ' http_=>"%s",'                                % paramDict['httpVersion']
    cmd += ' enable_tls=>"%s",'                           % paramDict['tlsEnabled']
    cmd += ' authentication_user=>"%s",'                  % paramDict['authenticationUsername']
    cmd += ' authentication_password=>"%s",'              % paramDict['authenticationPassword']
    cmd += ' authentication_use_initial_req=>"%s",'       % paramDict['authenticationUseInitialReq']
    cmd += ' number_requests_per_connection=>"%s",'       % paramDict['requestsPerConnection']
    cmd += ' delay_between_requests=>"%s",'               % paramDict['requestDelay']
    cmd += ' delay_between_requests_metrics=>"%s",'       % paramDict['requestDelayMetric']
    cmd += ' delay_between_connections=>"%s",'            % paramDict['connectionsDelay']
    cmd += ' delay_between_connections_metric=>"%s",'     % paramDict['connectionsDelayMetric']
    cmd += ' is_ignore_redirects_enabled=>"%s",'          % paramDict['ignoreRedirectsEnabled']
    cmd += ' is_connection_reset_enabled=>"%s",'          % paramDict['connectionResetEnabled']
    cmd += ' resource_list=>"%s",'                        % paramDict['resourceList']
    cmd += ' is_http_response_code_stats_enabled=>"%s",'  % paramDict['httpResponseCodeStats']
    cmd += ' is_keyword_substitution_enabled=>"%s",'      % paramDict['keywordSubstitutionEnabled']
    cmd += ' header_field_list=>"%s",'                    % paramDict['headerFieldList']
    cmd += ' is_acws_enabled=>"%s",'                      % paramDict['acwsEnabled']
    cmd += ' acws_username=>"%s",'                        % paramDict['acwsUsername']
    cmd += ' acws_user_group=>"%s",'                      % paramDict['acwsUsergroup']
    cmd += ' acws_license_key=>"%s",'                     % paramDict['acwsLicenseKey']
    cmd += ' acws_agent_version=>"%s"'                    % paramDict['acwsAgentVersion']
    cmd += '));'

    self._write(cmd)

  def dhcpv4ServerCreate(self, name, paramDict):
    """
    Creates a DHCPv4 server application. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):

    | *Group*                 | *Key*                   | *Value*                              |
    | *Application details*   | *host*                  | <host created with hostCreate>       |
    |                         | description             | <string> , *empty*                   |
    |                         | adminState              | _disable_ , _*enable*_               |
    | *IP address assignment* | *subnet*                | <IP address / mask> , *empty*        |
    |                         | *startIpAddress*        | <IP address> , *empty*               |
    |                         | numberOfIpAddresses     | _*1*_ , <number>                     |
    | *Client configuration*  | gatewayIp               | _IP address or *default*_            |
    |                         | dnsServer               | _valid IP address, default: *empty*_ |
    |                         | domain                  | <string> , *empty*                   |
    |                         | leaseTime               | <number> , _*infinite*_              |
    |                         | leaseTimeMetric         | _*secs*_ , _mins_ , _hrs_ , _days_   |
    |                         | rebindTime              | <number>, _infinite_ , *empty*       |
    |                         | rebindTimeMetric        | _*secs*_ , _mins_ , _hrs_ , _days_   |
    |                         | renewalTime             | <number>, infinite , *empty*         |
    |                         | renewalTimeMetric       | _*secs*_ , _mins_ , _hrs_ , _days_   |
    | *Server settings*       | broadcastDhcpOffer      | _*false*_ , _true_                   |
    |                         | relayAgentInfoInReplies | _*false*_ , _true_                   |
    """

    defaultParamDict = {
      'host':                     '',
      'description':              '',
      'adminState':               'enable',
      'subnet':                   '',
      'startIpAddress':           '',
      'numberOfIpAddresses':      '1',
      'gatewayIp':                'default',
      'dnsServer':                '',
      'domain':                   '',
      'leaseTime':                'infinite',
      'leaseTimeMetric':          'secs',
      'rebindTime':               '',
      'rebindTimeMetric':         'secs',
      'renewalTime':              '',
      'renewalTimeMetric':        'secs',
      'broadcastDhcpOffer':       'false',
      'relayAgentInfoInReplies':  'false',
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    paramDict['adminState'] = self._getValueFromDict(paramDict['adminState'], {
      'enable':   'Enabled',
      'disable':  'Disabled',
    })

    cmd  = '$Tg->Add(diversifEye::Dhcp4Server->new('
    cmd += ' name=>"%s",'                                 % name
    cmd += ' host=>"%s",'                                 % paramDict['host']
    cmd += ' description=>"%s",'                          % paramDict['description']
    cmd += ' administrative_state=>"%s",'                 % paramDict['adminState']
    cmd += ' subnet=>"%s",'                               % paramDict['subnet']
    cmd += ' start_ip_addr=>"%s",'                        % paramDict['startIpAddress']
    cmd += ' number_of_ip_addr=>"%s",'                    % paramDict['numberOfIpAddresses']
    cmd += ' use_default_gateway_ip=>"%s",'               % ('true' if paramDict['gatewayIp'] == 'default' else 'false')
    cmd += ' gateway_ip=>"%s",'                           % (paramDict['gatewayIp'] if paramDict['gatewayIp'] != 'default' else '')
    cmd += ' dns_server=>"%s",'                           % paramDict['dnsServer']
    cmd += ' domain=>"%s",'                               % paramDict['domain']
    cmd += ' infinite_lease_time=>"%s",'                  % ('true' if paramDict['leaseTime'] == 'infinite' else 'false')
    cmd += ' lease_time=>"%s",'                           % (paramDict['leaseTime'] if paramDict['leaseTime'] != 'infinite' else '')
    cmd += ' lease_time_metric=>"%s",'                    % paramDict['leaseTimeMetric']
    cmd += ' infinite_rebinding_time=>"%s",'              % ('true' if paramDict['rebindTime'] == 'infinite' else 'false')
    cmd += ' rebinding_time=>"%s",'                       % (paramDict['rebindTime'] if paramDict['rebindTime'] != 'infinite' else '')
    cmd += ' rebinding_time_metric=>"%s",'                % paramDict['rebindTimeMetric']
    cmd += ' infinite_renewal_time=>"%s",'                % ('true' if paramDict['renewalTime'] == 'infinite' else 'false')
    cmd += ' renewal_time=>"%s",'                         % (paramDict['renewalTime'] if paramDict['renewalTime'] != 'infinite' else '')
    cmd += ' renewal_time_metric=>"%s",'                  % paramDict['renewalTimeMetric']
    cmd += ' broadcast_dhcp_offer_msg=>"%s",'             % paramDict['broadcastDhcpOffer']
    cmd += ' include_relay_agent_info_in_replies=>"%s",'  % paramDict['relayAgentInfoInReplies']
    cmd += '));'

    self._write(cmd)

  def pppoeServerCreate(self, name, paramDict):
    """
    Creates a PPPoE server application. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):

    | *Group*                 | *Key*                       | *Value*                        |
    | *Application details*   | *host*                      | <host created with hostCreate> |
    |                         | description                 | <string> , *empty*             |
    |                         | adminState                  | _disable_ , _*enable*_         |
    | *IPCP settings*         | *startIpAddress*            | <IP address / mask> , *empty*  |
    |                         | numberOfIpAddresses         | _*100*_ , <number>             |
    | *PPPoE settings*        | serviceName                 | <string> , *empty*             |
    |                         | accessConcentrator          | <string< , *empty*             |
    |                         | mru                         | _*1492*_ , <number>            |
    |                         | isPapSupported              | _*false*_ , _true_             |
    |                         | isChapSupported             | _*false*_ , _true_             |
    |                         | isAcCookieUsed              | _false_ , _*true*_             |
    |                         | isMagicNumberUsed           | _false_ , _*true*_             |
    |                         | doubleRetransmitTime        | _*false*_ , _true_             |
    |                         | retransmitTimer             | _*3000*_ , <number>            |
    |                         | retransmitTimerMetric       | _*ms*_ , _secs_ , _mins_       |
    |                         | lcpLinkTestRequestMode      | _none_ , _*echo*_ , _discard_  |
    |                         | lcpLinkTestPayloadSize      | _*1492*_ , <number>, <probability distribution profile created with probabilityDistributionCreate>  |
    |                         | lcpLinkTestInterval         | _*30*_ , <number>              |
    |                         | lcpLinkTestIntervalMetric   | _ms_ , _*secs*_ , _mins_       |
    |                         | startSessionId              | _*1*_ , <number>               |

    """

    defaultParamDict = {
      # application settings
      'host':                       '',
      'description':                '',
      'adminState':                 'enable',
      #'transportPort':              '',
      #'qos':                        '0',
      'startSessionId':             '1',
      'startIpAddress':             '',
      'numberOfIpAddresses':        '100',
      #'startAfter':                 '',
      #'startAfterMetric':           'secs',
      #'stopAfter':                  '',
      #'stopAfterMetric':            'secs',
      'pppoeSettings':              '',

      # pppoe Settings
      'forIpv6':                    'false',                # true, false
      'username':                   '',                     # string, PsAlnum (not implemented)
      'password':                   '',                     # string, PsAlnum (not implemented)
      'serviceName':                '',                     # string, PsAlnum (not implemented)
      'accessConcentrator':         '',                     # string, PsAlnum (not implemented)
      'mru':                        '1492',                 # int
      'isPapSupported':             'false',                # true, false
      'isChapSupported':            'false',                # true, false
      'checkHostUnique':            'true',                 # true, false
      'isAcCookieUsed':             'true',                 # true, false
      'isMagicNumberUsed':          'true',                 # true, false
      'doubleRetransmitTime':       'false',                # true, false
      'retransmitTimer':            '3000',                 # int
      'retransmitTimerMetric':      'ms',                   # ms, secs, mins
      'lcpLinkTestRequestMode':     'echo',                 # none, echo, discard
      'lcpLinkTestPayloadSize':     '1492',                 # int
      'lcpLinkTestInterval':        '30',                   # int
      'lcpLinkTestIntervalMetric':  'secs',                 # ms, secs, mins
      'reconnectAfterFailure':      'true',                 # true, false
      'requestPrimaryDns':          'false',                # true, false
      'requestSecondaryDns':        'false',                # true, false
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    paramDict['adminState'] = self._getValueFromDict(paramDict['adminState'], {
      'enable':   'Enabled',
      'disable':  'Disabled',
    })

    pppoeConfig = self._pppoeSettingsCreate(paramDict)

    cmd  = '$Tg->Add(diversifEye::PppoeServer->new('
    cmd += ' name=>"%s",'                                 % name
    cmd += ' host=>"%s",'                                 % paramDict['host']
    cmd += ' description=>"%s",'                          % paramDict['description']
    cmd += ' administrative_state=>"%s",'                 % paramDict['adminState']
    cmd += ' start_session_id=>"%s",'                     % paramDict['startSessionId']
    cmd += ' ipcp_start_ip_address=>"%s",'                % paramDict['startIpAddress']
    cmd += ' ipcp_no_of_available_ip_addresses=>"%s",'    % paramDict['numberOfIpAddresses']
    cmd += ' pppoe_settings=>%s,'                         % pppoeConfig
    cmd += '));'

    self._write(cmd)

  def igmpGroupListCreate(self, name, paramDict):
    """
    Creates a multicast group list. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):

    | *Key*                     | *Value*                                      |
    | description               | <string> , *empty*                           |
    | ipAddressType             | _*IPv4*_ , _IPv6_                            |
    | mcGroupList               | <list of mcGroupList dictionaries> , *empty* |

    mcGroupList dictionary:
    | *Key*                     | *Value*      |
    | *address*                 | <IP address> |
    | *srcPort*                 | <number>     |
    | *dstPort*                 | <number>     |
    """

    defaultParamDict = {
      'description':    '',
      'ipAddressType':  'IPv4',
      'mcGroupList':    []
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    # create perl command
    cmd  = '$Tg->Add(diversifEye::MulticastGroupList->new('
    cmd += ' name=>"%s",'                 % name
    cmd += ' description=>"%s",'          % paramDict['description']
    cmd += ' ip_address_type=>"%s",'      % paramDict['ipAddressType']
    cmd += ')'

    for mcGroup in paramDict['mcGroupList']:
      cmd += '->Add(diversifEye::MulticastGroup->new('
      cmd += ' group_address=>"%s",'      % mcGroup['address']
      cmd += ' source_port=>"%s",'        % mcGroup['srcPort']
      cmd += ' destination_port=>"%s"'    % mcGroup['dstPort']
      cmd += '))'

    cmd += ');'

    self._write(cmd)

  def igmpFilterListCreate(self, name, paramDict):
    """
    Creates a IP filter list. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):

    | *Key*                       | *Value*                          |
    | description                 | <string> , *empty*               |
    | ipAddressType               | _*IPv4*_ , _IPv6_                |
    | ipAddressList               | <list of IP addresses> , *empty* |
    """

    defaultParamDict = {
      'description':    '',
      'ipAddressType':  'IPv4',
      'ipAddressList':  []
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    # create perl command
    cmd  = '$Tg->Add(diversifEye::IpAddressFilterList->new('
    cmd += ' name=>"%s",'                 % name
    cmd += ' description=>"%s",'          % paramDict['description']
    cmd += ' ip_address_type=>"%s",'      % paramDict['ipAddressType']
    cmd += ')'

    for ipAddress in paramDict['ipAddressList']:
      cmd += '->Add(diversifEye::IpAddressFilter->new('
      cmd += ' ip_address=>"%s",' % ipAddress
      cmd += '))'

    cmd += ');'

    self._write(cmd)

  def statisticsGet(self, statsType, entityType, name, columnLabel, presentation):
    """
    Gets a statistic value from an entity specified by _name_
    - statsType: normal|fine
    - entityType: aggregate|host|application|interface|card
    - name: string, if entityType is 'aggregate' concatenate the name of the aggregate group with the aggregate type (e.g. 'Host') using '_'
    - columnLabel: desired statistic, see gui column labels (without metric, e.g. /s)
    - presentation: rate|cu(multative)|(per-)int(erval)
    """

    # see "cli help ColumnLabels"

    if   presentation == 'rate':
      columnLabel = columnLabel.strip() + '/s'
    elif 'cu' in presentation:
      columnLabel = columnLabel.strip() + ' cu'
    elif 'int' in presentation:
      columnLabel = columnLabel.strip()
    else:
      raise AssertionError('unknown presentation value: %s' % presentation)

    stat = self._execSshCommand('cli -u %s getStat %s "%s" %s %s' % (self._tvmcUser, name, columnLabel, statsType.capitalize(), entityType.capitalize()))

    # try to convert to integer/float
    if   re.match('^\d+$', stat):
      stat = int(stat)
    elif re.match('^\d+\.\d+$', stat):
      stat = float(stat)
    else:
      stat = stat.strip()

    return stat

  def statisticsSave(self, localPath='', optionsDict=None):
    """
    Creates a zip file containing csv result files on the TVM-C and downloads it to the local PC.

    Parameters:
    - localPath:   <string> (optional), path where the zip file should be saved. Default file name is "csvStatistics.zip"
                   if no file name in localPath is given. Default _localPath_ is Robot's output directory
    - optionsDict: <dictionary> (optional), contains the options:value pairs. The default options dictionary is set as following:
    | {
    |   'cumulative': 'true',
    |   'extendedMetadata': 'false',
    | }

    | *Option*           | *Value*              | *Comment* |
    | after              | <YYYY-MM-DD HH:MM:SS> , <integer representing milliseconds since the 1970 epoch> | Only save samples or events with timestamp strictly greater than this value. Default: All available samples, but if _samples_ is specified, the most recent samples are saved, limited by number to the value of _samples_ |
    | aggregateGroup     | <string>             | Similar to _entityName_ but is a full match for the name of the statistics aggregate group, if any, with which the entity is associated |
    | columns            | <string>             | Comma-separated list of column labels specifying the columns to save and how they are to be presented. See "cli help ColumnLabels" for more information. Default: Save all available columns with default presentation |
    | *cumulative*       | _false_ , _*true*_   | If true, the default column presentation is as a cumulative value (where the column supports it) instead of a rate. The default presentation of a column may be overridden by the _columns_ option |
    | description        | <string>             | Similar to _entityName_ but is a full match for the _description_ attribute |
    | entityName         | <string>             | A Java-style regular expression that selects entities whose name attribute is fully matched by the regex. For example: 'client.*' selects entities whose name begins with 'client' and 'hc[0-4][0-9]' selects entities whose name begins with 'hc' and ends with a double digit number between 0 and 49. Default: Match all |
    | entityType         | _aggregate_ , _application_ , _host_ , _interface_ , _meta_ , _testGroup_ | Similar to _entityName_ but is a full match for the _entityType_ attribute of which typical values are 'Aggregate', 'Host', 'Application', 'Interface' |
    | events             | _false_ , _*true*_   | If true, relevant threshold events are saved. Can override _true_ with Stats.ZipfileEvents=false in MasterServer*.props. Only events associated with test entities whose stats are being saved are included, and if options _after_ and/or _samples_ are used to restrict the stats saved to a particular period of time, events are restricted to the same time period |
    | *extendedMetadata* | _*false*_ , _true_   | Zipfile contains extended metadata if true. Can override _true_ with Stats.ZipfileExtendedMetadata=false in MasterServer*.props |
    | samples            | <integer>            | The maximum number of samples to save (per entity). Default: All available samples, but possibly limited by timestamp if _after_ is specified. Also controls the number of events saved (see the _events_ option) |
    | statsType          | _fine_ or _*normal*_ | A Java-style regular expression fully matching available statistics types. Typical values _fine_ or _normal_  |

    *Example*
    | ${options}     | Create Dictionary            | cumulative | true | entityType | aggregate |
    | statisticsSave |                              |            | # creates <Robot output dir>/csvStatistics.zip |
    | statisticsSave | /home/sff00009               | ${options} | # creates /home/sff00009/csvStatistics.zip |
    | statisticsSave | /home/sff00009/              | ${options} | # creates /home/sff00009/csvStatistics.zip |
    | statisticsSave | /home/sff00009/myCsvFile.zip | ${options} | # creates /home/sff00009/myCsvFile.zip |
    """
    if not optionsDict: optionsDict = {}
    if 'cumulative'       not in optionsDict.keys(): optionsDict['cumulative'] =       'true'
    if 'extendedMetadata' not in optionsDict.keys(): optionsDict['extendedMetadata'] = 'false'

    optionList = []
    if isinstance(optionsDict, dict):
      for option, value in optionsDict.iteritems():
        if   option in ['columns']:
          optionList.append('%s="%s"' % (option[0].upper() + option[1:], value))
        elif option in ['entityType', 'statsType']:
          optionList.append('%s=%s' % (option[0].upper() + option[1:], value.title()))
        else:
          optionList.append('%s=%s' % (option[0].upper() + option[1:], value))
    optionList = ' '.join(optionList)

    if not localPath:
      localPath = os.path.join(BuiltIn().replace_variables('${OUTPUTDIR}'), 'csvStatistics.zip')

    remotePath = '/tmp/csvStatistics.zip'

    self._execSshCommand('cli -u %s saveStats %s %s' % (self._tvmcUser, optionList, remotePath))
    self._scpGetFile(remotePath, localPath)
    self._execSshCommand('rm %s' % remotePath)

  def statisticsGetAll(self, optionsDict=None, metadata='false'):
    """
    Returns a dictionary containing the tables.

    Parameters:
    - optionsDict: <dictionary> (optional); contains the options:value pairs. The default options dictionary is set as following:
    | {
    |   'cumulative': 'true',
    |   'extendedMetadata': 'false',
    | }
    - metadata: _*false*_ , _true_ ; set to true if the dictionary shall contain the meta data.

    *NOTE*: It is strictly recommended not to put meta data into the dictionary due to the huge amount of meta data.

    | *Option*           | *Value*              | *Comment* |
    | after              | <YYYY-MM-DD HH:MM:SS> , <integer representing milliseconds since the 1970 epoch> | Only save samples or events with timestamp strictly greater than this value. Default: All available samples, but if _samples_ is specified, the most recent samples are saved, limited by number to the value of _samples_ |
    | aggregateGroup     | <string>             | Similar to _entityName_ but is a full match for the name of the statistics aggregate group, if any, with which the entity is associated |
    | columns            | <string>             | Comma-separated list of column labels specifying the columns to save and how they are to be presented. See "cli help ColumnLabels" for more information. Default: Save all available columns with default presentation |
    | *cumulative*       | _false_ , _*true*_   | If true, the default column presentation is as a cumulative value (where the column supports it) instead of a rate. The default presentation of a column may be overridden by the _columns_ option |
    | description        | <string>             | Similar to _entityName_ but is a full match for the _description_ attribute |
    | entityName         | <string>             | A Java-style regular expression that selects entities whose name attribute is fully matched by the regex. For example: 'client.*' selects entities whose name begins with 'client' and 'hc[0-4][0-9]' selects entities whose name begins with 'hc' and ends with a double digit number between 0 and 49. Default: Match all |
    | entityType         | _aggregate_ , _application_ , _host_ , _interface_ , _meta_ , _testGroup_ | Similar to _entityName_ but is a full match for the _entityType_ attribute of which typical values are 'Aggregate', 'Host', 'Application', 'Interface' |
    | events             | _false_ , _*true*_   | If true, relevant threshold events are saved. Can override _true_ with Stats.ZipfileEvents=false in MasterServer*.props. Only events associated with test entities whose stats are being saved are included, and if options _after_ and/or _samples_ are used to restrict the stats saved to a particular period of time, events are restricted to the same time period |
    | *extendedMetadata* | _*false*_ , _true_   | Zipfile contains extended metadata if true. Can override _true_ with Stats.ZipfileExtendedMetadata=false in MasterServer*.props |
    | samples            | <integer>            | The maximum number of samples to save (per entity). Default: All available samples, but possibly limited by timestamp if _after_ is specified. Also controls the number of events saved (see the _events_ option) |
    | statsType          | _fine_ or _*normal*_ | A Java-style regular expression fully matching available statistics types. Typical values _fine_ or _normal_  |

    *Example*
    | ${options} | Create Dictionary | cumulative | true | entityType | aggregate |
    | ${stats}   | statisticsGetAll  | ${options} |
    """
    stats   = {}
    tempDir = tempfile.mkdtemp()

    try:
      # save stats on tvm-c and copy them to local machine
      self.statisticsSave(tempDir, optionsDict)
      # extract zip file
      zip = zipfile.ZipFile(os.path.join(tempDir, 'csvStatistics.zip'))
      zip.extractall(tempDir)

      for statsFolder in glob.glob(os.path.join(tempDir, '*/')):
        # statFolder ends with directory separator
        head, entityType = os.path.split(statsFolder[:-1]) # get the folder name in entityType

        stats[entityType.lower()] = {}

        # process all csv files
        for statsFile in glob.glob(os.path.join(tempDir, entityType, '') + '*.csv'): # empty element in join for leading '/'
          # get file/path elements
          head, tail = os.path.split(statsFile) # path + filename (w/ extension)
          root, ext  = os.path.splitext(tail)   # filename (w/o ext) + extension

          if root == 'Meta' and metadata.lower() == 'false':
            continue

          entityType = entityType.lower()

          root = root.replace('.Normal', '').replace('.Fine', '').replace(' cu', '')

          stats[entityType][root] = defaultdict(list)

          f = open(statsFile)
          csvReader = csv.DictReader(f)

          # this will append all rows from the csv to our dict as list of values of key as table column
          for row in csvReader:
            for key, value in row.items():
              stats[entityType][root][key].append(value)

          f.close()
      zip.close()
    except Exception as e:
      raise AssertionError('error processing csv: %s' % e.message)
    finally:
      shutil.rmtree(tempDir)
      return stats

  def igmpClientCreate(self, name, paramDict):
    """
    Creates a PPPoE server application. Content of _paramDict_ (mandatory keys are marked *bold*, default values are marked as *bold*):

    | *Group*                 | *Key*                       | *Value*                                                                                             |
    | *Application details*   | *host*                      | <name of host created with hostCreate>                                                              |
    |                         | numberOfClients             | _*1*_ , <number>                                                                                    |
    |                         | provisioningMode            | _*singleAppPerRow*_ , _scaledEntity_                                                                |
    |                         | mediaTransport              | _*RTP*_ , _MPEG2-TS/RTP_ , _MPEG2-TS_                                                               |
    |                         | description                 | <string> , *empty*                                                                                  |
    |                         | qos                         | _*0*_ , <number>                                                                                    |
    | *Client details*        | igmpVersion                 | _IGMPv1_ , _*IGMPv2*_ , _IGMPv3_                                                                    |
    |                         | routerAlert                 | _*false*_ , _true_                                                                                  |
    |                         | groupSelection              | _*groupList*_ , _specificGroup_                                                                     |
    |                         | groupList                   | <group list created with igmpGroupListCreate> , *empty* (required if groupSelection = _groupList_   |
    |                         | mcGroupAddress              | < multicast IP addess> , _*239.252.1.1*_ (required if groupSelection = _specificGroup_ )            |
    |                         | srcPort                     | <*groupList*, <group> (required if groupSelection = _specificGroup_ )                               |
    |                         | dstPort                     | <*groupList*, <group> (required if groupSelection = _specificGroup_ )                               |
    |                         | acceptAnySrcPort            | _*false*_ , _true_                                                                                  |
    |                         | acceptAnyDstPort            | _*false*_ , _true_                                                                                  |
    | *Join details*          | joinGroups                  | _false_ , _*true*_                                                                                  |
    |                         | joinStrategy                | _*sequential*, random, concurrent_                                                                  |
    |                         | leaveGroup                  | _*afterDuration*, never, afterJoin_                                                                 |
    |                         | joinDuration                | _*980*_ , <number> , <probability distribution profile created with probabilityDistributionCreate>  |
    |                         | joinDurationMetric          | _*ms*, secs, mins, hrs_                                                                             |
    |                         | rejoinDelay                 | _*20*_ , <number> , <probability distribution profile created with probabilityDistributionCreate>   |
    |                         | rejoinDelayMetric           | _*ms*, secs, mins, hrs_                                                                             |
    | *Advanced settings*     | joinReportCount             | _*2*_ , <number>                                                                                    |
    |                         | joinReportInterval          | _*1000*_ , <number> , <probability distribution profile created with probabilityDistributionCreate> |
    |                         | joinReportIntervalMetric    | _*ms*_ , _secs_ , _mins_                                                                            |
    |                         | rejoinAfterFailure          | _*false*_ , _true_                                                                                  |
    |                         | joinTimeout                 | _*2*_ , <number>                                                                                    |
    |                         | joinTimeoutMetric           | _ms, *secs*, mins_                                                                                  |
    |                         | enableUmr                   | unsolicited membership report, _*false*_ , _true_                                                   |
    |                         | umrDelay                    | _*1*_ , <number>, <probability distribution profile created with probabilityDistributionCreate>     |
    |                         | umrDelayMetric              | _*ms*_ , _secs_ , _mins_                                                                            |
    |                         | maxQrTimeOverride           | _*false*_ , _true_                                                                                  |
    |                         | maxQrTime                   | <number> , <probability distribution profile created with probabilityDistributionCreate> , *empty*  |
    |                         | maxQrTimeMetric             | _ms, *secs*, mins_                                                                                  |
    |                         | multipleGroupsPerReport     | _*false*_ , _true_                                                                                  |
    |                         | groupsPerReport             | _*2*_ , <number>                                                                                    |
    | *Filter details*        | enableFilter                | _*false*_ , _true_                                                                                  |
    |                         | filterType                  | _*include*, exclude_                                                                                |
    |                         | sourceIpFilterList          | _name of group list created with igmpFilterListCreate, default: empty_                              |
    | *Additional details*    | startAfter                  | <number> , <probability distribution profile created with probabilityDistributionCreate> , *empty*  |
    |                         | startAfterMetric            | _*ms*_ , _secs_ , _mins_                                                                            |
    |                         | stopAfter                   | <number> , <probability distribution profile created with probabilityDistributionCreate> , *empty*  |
    |                         | stopAfterMetric             | _*secs*_ , _mins_ , _hours_                                                                         |
    |                         | aggregateGroup              | <aggregate group created with aggregateGroupCreate> , _*Default*_                                   |
    |                         | passiveAnalysis             | _*false*_ , _true_                                                                                  |
    |                         | playoutJitter               | _*300*_ , <number>                                                                                  |
    |                         | playoutJitterMetric         | _*ms*_ , _secs_                                                                                     |
    |                         | maxJitter                   | _*900*_ , <number>                                                                                  |
    |                         | maxJitterMetric             | _*ms*_ , _secs_                                                                                     |
    | *Statistics*            | normalStats                 | _false_ , _*true*_                                                                                  |
    |                         | fineStats                   | _*false*_ , _true_                                                                                  |
    |                         | leaveTimeStats              | _*false*_ , _true_                                                                                  |
    |                         | enableMaximumLeaveTime      | _*false*_ , _true_                                                                                  |
    |                         | maximumLeaveTime            | _*2000*_ , <number>                                                                                 |
    |                         | maximumLeaveTimeMetric      | _*ms*_ , _secs_                                                                                     |
    |                         | enableLeaveTimeout          | _false_ , _*true*_                                                                                  |
    |                         | leaveTimeout                | _*2000*_ , <number>                                                                                 |
    |                         | leaveTimeoutMetric          | _*ms*_ , _secs_                                                                                     |
    """

    defaultParamDict = {
      'host':                       '',
      'description':                '',
      'adminState':                 'enable',
      'serviceState':               'inService',
      'numberOfClients':            '1',
      'normalStats':                'true',
      'fineStats':                  'false',
      'qos':                        '0',
      'startAfter':                 '0',
      'startAfterMetric':           'secs',
      'stopAfter':                  '',
      'stopAfterMetric':            'secs',
      'transportPort':              '',
      'aggregateGroup':             '',
      'routerAlert':                'false',          # true, false
      'mediaTransport':             'RTP',            # RTP, MPEG2-TS/RTP, MPEG2-TS
      'igmpVersion':                'IGMPv2',         # IGMPv2, IGMPv1, IGMPv3
      'groupSelection':             'groupList',      # groupList, specificGroup
      'groupList':                  '',               # name of group list, created with igmpGroupListCreate
      'mcGroupAddress':             '239.252.1.1',
      'srcPort':                    '',               # [Integer (0-65535)]. Scalable. Suggested scalers: [PsInt]
      'dstPort':                    '',               # [Integer (0-65535)]. Scalable. Suggested scalers: [PsInt]
      'acceptAnySrcPort':           'false',          # true, false
      'acceptAnyDstPort':           'false',          # true, false
      'joinReportInterval':         '1000',
      'joinReportIntervalMetric':   'ms',
      'joinReportCount':            '2',
      'enableUmr':                  'false',           # true, false
      'umrDelay':                   '1',              # MR = MembershipReport
      'umrDelayMetric':             'ms',             # ms, secs, mins
      'maxQrTimeOverride':          'false',          # true, false
      'maxQrTime':                  '',
      'maxQrTimeMetric':            'secs',           # ms, secs, mins
      'rejoinAfterFailure':         'false',          # true, false
      'joinTimeout':                '2',
      'joinTimeoutMetric':          'secs',           # ms, secs, mins
      'sourceIpFilterList':         '',               # name of filter list, created with igmpFilterListCreate
      'filterType':                 'include',        # include, exclude
      'enableFilter':               'false',          # true, false
      'joinGroups':                 'true',           # true, false
      'joinStrategy':               'sequential',     # sequential, random, concurrent
      'leaveGroup':                 'afterDuration',  # afterDuration, never, afterJoin
      'joinDuration':               '980',
      'joinDurationMetric':         'ms',             # ms, secs, mins, hrs
      'rejoinDelay':                '20',
      'rejoinDelayMetric':          'ms',             # ms, secs, mins, hrs
      'multipleGroupsPerReport':    'false',          # true, false
      'groupsPerReport':            '2',
      'passiveAnalysis':            'false',          # true, false
      'passiveAnalysisStatistics':  'false',          # true, false
      'firstCompleteIframeStats':   'false',          # true, false
      'playoutJitter':              '300',
      'playoutJitterMetric':        'ms',             # ms, secs
      'maxJitter':                  '900',
      'maxJitterMetric':            'ms',             # ms, secs
      'videoCodec':                 'MPEG',           # Static │ JPEG │ MPEG │ H.261 │ H.263 │ H.263+ │ H.264 │MPEG-4│VC-1]. NB: Static is only available if media_stream is "RTP"
      'analyzeVideoStream':         'true',           # true, false
      'videoPid':                   '',
      'analyzeAudioStream':         'false',          # true, false
      'audioCodec':                 'MPEG-1 Layer 1', # [AC-3│MPEG-1 Layer 1│MPEG-1 Layer 2│MPEG-1 Layer 3│MPEG-2 AAC│MPEG-4 AAC│MPEG-4 Low Delay AAC│MPEG-4 High Efficiency AAC]
      'audioPid':                   '',
      'autoDeterminePid':           'true',           # true, false
      'leaveTimeStats':             'false',          # true, false. Controls Leave Timing within Extended Join/Leave statistics (always enabled).
      'enableMaximumLeaveTime':     'false',          # true, false
      'maximumLeaveTime':           '2000',
      'maximumLeaveTimeMetric':     'ms',             # ms, secs
      'enableLeaveTimeout':         'true',           # true, false
      'leaveTimeout':               '2000',
      'leaveTimeoutMetric':         'ms',             # ms, secs
      'provisioningMode':           'singleAppPerRow' # singleAppPerRow, scaledEntity
    }

    serviceStateDict = {
      'inService':    'In Service',
      'outOfService': 'Out of Service'
    }

    provisioningModeDict = {
      'singleAppPerRow': 'Single App per Row',
      'scaledEntity':    'Scaled Entity'
    }

    groupSelectionDict = {
      'groupList':      'Group List',
      'specificGroup':  'Specific Group'
    }

    leaveGroupDict = {
      'afterDuration':  'After Duration',
      'never':          'Never',
      'afterJoin':      'After Join'
    }

    paramDict = self._getDefaultParams(paramDict, defaultParamDict)

    paramDict['adminState'] = self._getValueFromDict(paramDict['adminState'], {
      'enable':   'Enabled',
      'disable':  'Disabled',
    })

    if paramDict['provisioningMode'] == 'singleAppPerRow' and paramDict['numberOfClients'] == '1':
      paramDict['scaleFactor'] = ''
    else:
      paramDict['scaleFactor'] = paramDict['numberOfClients']

    cmd  = '$Tg->Add(diversifEye::IgmpClient->new('
    cmd += ' name=>"%s",'                                 % name
    cmd += ' host=>"%s",'                                 % paramDict['host']
    cmd += ' description=>"%s",'                          % paramDict['description']
    cmd += ' administrative_state=>"%s",'                 % paramDict['adminState']
    cmd += ' service_state=>"%s",'                        % serviceStateDict[paramDict['serviceState']]
    cmd += ' scale_factor=>"%s",'                         % paramDict['scaleFactor']
    cmd += ' transport_port=>"%s",'                       % paramDict['transportPort']
    cmd += ' provisioning_mode=>"%s",'                    % provisioningModeDict[paramDict['provisioningMode']]
    cmd += ' is_normal_stats_enabled=>"%s",'              % paramDict['normalStats']
    cmd += ' is_fine_stats_enabled=>"%s",'                % paramDict['fineStats']
    cmd += ' qos=>"%s",'                                  % paramDict['qos']
    cmd += ' start_after=>"%s",'                          % paramDict['startAfter']
    cmd += ' start_after_metric=>"%s",'                   % paramDict['startAfterMetric']
    cmd += ' stop_after=>"%s",'                           % paramDict['stopAfter']
    cmd += ' stop_after_metric=>"%s",'                    % paramDict['stopAfterMetric']
    cmd += ' aggregate_group=>"%s",'                      % paramDict['aggregateGroup']
    cmd += ' router_alert=>"%s",'                         % paramDict['routerAlert']
    cmd += ' media_transport=>"%s",'                      % paramDict['mediaTransport']
    cmd += ' interested_group_selection=>"%s",'           % groupSelectionDict[paramDict['groupSelection']]
    cmd += ' interested_group_list=>"%s",'                % paramDict['groupList']
    cmd += ' multicast_group_address=>"%s",'              % paramDict['mcGroupAddress']
    cmd += ' source_port=>"%s",'                          % paramDict['srcPort']
    cmd += ' destination_port=>"%s",'                     % paramDict['dstPort']
    cmd += ' accept_from_any_src_port=>"%s",'             % paramDict['acceptAnySrcPort']
    cmd += ' accept_to_any_dst_port=>"%s",'               % paramDict['acceptAnyDstPort']
    cmd += ' join_report_delay=>"%s",'                    % paramDict['joinReportInterval']
    cmd += ' join_report_delay_metric=>"%s",'             % paramDict['joinReportIntervalMetric']
    cmd += ' join_report_count=>"%s",'                    % paramDict['joinReportCount']
    cmd += ' enable_unsolicited_mr=>"%s",'                % paramDict['enableUmr']
    cmd += ' delay_between_unsolicited_mr=>"%s",'         % paramDict['umrDelay']
    cmd += ' delay_between_unsolicited_mr_metric=>"%s",'  % paramDict['umrDelayMetric']
    cmd += ' enable_override_of_max_qr_time=>"%s",'       % paramDict['maxQrTimeOverride']
    cmd += ' maximum_qr_time=>"%s",'                      % paramDict['maxQrTime']
    cmd += ' maximum_qr_time_metric=>"%s",'               % paramDict['maxQrTimeMetric']
    cmd += ' enable_rejoin_after_failure=>"%s",'          % paramDict['rejoinAfterFailure']
    cmd += ' join_timeout=>"%s",'                         % paramDict['joinTimeout']
    cmd += ' join_timeout_metric=>"%s",'                  % paramDict['joinTimeoutMetric']
    cmd += ' source_ipaddress_filter_list=>"%s",'         % paramDict['sourceIpFilterList']
    cmd += ' filter_type=>"%s",'                          % paramDict['filterType'].capitalize()
    cmd += ' filter_enabled=>"%s",'                       % paramDict['enableFilter']
    cmd += ' join_groups=>"%s",'                          % paramDict['joinGroups']
    cmd += ' join_strategy=>"%s",'                        % paramDict['joinStrategy'].capitalize()
    cmd += ' leave_group=>"%s",'                          % leaveGroupDict[paramDict['leaveGroup']]
    cmd += ' duration_of_join=>"%s",'                     % paramDict['joinDuration']
    cmd += ' duration_of_join_metric=>"%s",'              % paramDict['joinDurationMetric']
    cmd += ' delay_before_rejoin=>"%s",'                  % paramDict['rejoinDelay']
    cmd += ' delay_before_rejoin_metric=>"%s",'           % paramDict['rejoinDelayMetric']
    cmd += ' enable_multiple_groups_per_report=>"%s",'    % paramDict['multipleGroupsPerReport']
    cmd += ' groups_per_report=>"%s",'                    % paramDict['groupsPerReport']
    cmd += ' configure_passive_analysis=>"%s",'           % paramDict['passiveAnalysis']
    cmd += ' enable_passive_analysis_statistics=>"%s",'   % paramDict['passiveAnalysisStatistics']
    cmd += ' first_complete_iframe_stats=>"%s",'          % paramDict['firstCompleteIframeStats']
    cmd += ' playout_jitter=>"%s",'                       % paramDict['playoutJitter']
    cmd += ' playout_jitter_metric=>"%s",'                % paramDict['playoutJitterMetric']
    cmd += ' max_jitter=>"%s",'                           % paramDict['maxJitter']
    cmd += ' max_jitter_metric=>"%s",'                    % paramDict['maxJitterMetric']
    cmd += ' video_codec=>"%s",'                          % paramDict['videoCodec']
    cmd += ' analyse_video_stream=>"%s",'                 % paramDict['analyzeVideoStream']
    cmd += ' video_pid=>"%s",'                            % paramDict['videoPid']
    cmd += ' analyse_audio_stream=>"%s",'                 % paramDict['analyzeAudioStream']
    cmd += ' audio_codec=>"%s",'                          % paramDict['audioCodec']
    cmd += ' audio_pid=>"%s",'                            % paramDict['audioPid']
    cmd += ' auto_determine_pid=>"%s",'                   % paramDict['autoDeterminePid']
    cmd += ' enable_extended_leave_statistics=>"%s",'     % paramDict['leaveTimeStats']
    cmd += ' enable_maximum_leave_time=>"%s",'            % paramDict['enableMaximumLeaveTime']
    cmd += ' maximum_leave_time=>"%s",'                   % paramDict['maximumLeaveTime']
    cmd += ' maximum_leave_time_metric=>"%s",'            % paramDict['maximumLeaveTimeMetric']
    cmd += ' enable_leave_timeout=>"%s",'                 % paramDict['enableLeaveTimeout']
    cmd += ' leave_timeout_metric=>"%s",'                 % paramDict['leaveTimeout']
    cmd += ' leave_timeout_metric=>"%s",'                 % paramDict['leaveTimeoutMetric']
    cmd += ' igmp_version=>"%s",'                         % paramDict['igmpVersion']
    cmd += '));'

    self._write(cmd)

if __name__ == '__main__':
  """
  Start this module as Remote Library. This module must be executed on the
  remote machine before using the remote library on the local machine.

  Call one of these options to do this:

      python Shenick.py --controller=IPADDRESS --user=NAME --port=NUM
      ./Shenick.py      --controller=IPADDRESS --user=NAME --port=NUM

  Commandline arguments:

      controller ... IP address of Shenick Controller
      user       ... Name of user to be used
      port       ... Server port

  Example:

      python Shenick.py --controller=10.0.3.33 --user=robot --port=1234

  Use 'Stop Remote Server' keyword in Robot to stop remote server.
  Or use these commands to test and stop remote server on remote machine.

      python -m robotremoteserver test 127.0.0.1:PORT
      python -m robotremoteserver stop 127.0.0.1:PORT

  See also: https://github.com/robotframework/PythonRemoteServer

  Note that module 'robotremoteserver.py' must be found in builtin path or
  user pythonpath variable. A possible option was to put this module into
  PYTHON/Lib.
  """
  import argparse
  from robotremoteserver import RobotRemoteServer

  # create commandline parser
  parser = argparse.ArgumentParser(
    # use special formatter for dumping default values on help
    formatter_class = argparse.ArgumentDefaultsHelpFormatter)

  # add parser options
  parser.add_argument("-c", "--controller", required=True, help="IP address of Shenick Controller")

  parser.add_argument("-u", "--user", default="robot", help="User to be used")

  parser.add_argument("-p", "--port", type=int, default=8280, help="Server port")

  # parse commandline
  parsed = parser.parse_args()

  # run server
  RobotRemoteServer(Shenick(parsed.controller, parsed.user), "", parsed.port)

  #RobotRemoteServer(Shenick(sys.argv[1]),  host='', port=sys.argv[2])
