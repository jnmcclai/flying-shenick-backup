*** Settings ***
Library           %{TA_LIB}/libraries/robot/shenick/Shenick.py    192.168.0.2
Library           Collections

*** Test Cases ***
hosts
    Test Group Create    ${TEST_NAME}
    # tcp characteristics
    Probability Distribution Create    myProfile    1-5:10    20:40    30-50:50
    ${tcpParamDict}    Create Dictionary    timerProfile    myProfile    maxSegmentSize    myProfile    useSackWhenPermitted
    ...    true
    Tcp Characteristics Create    myTcpCharacteristicsProfile    ${tcpParamDict}
    ${bandwidthRateLimitDict}    Create Dictionary    rateLimit    1234
    Bandwidth Rate Limit Create    myBandwidthLimit    ${bandwidthRateLimitDict}
    # external host
    ${generalParamDict}    Create Dictionary    type    externalHost    ipAddress    1.1.1.1/24
    Host Create    myExternalHost    ${generalParamDict}    ${None}
    # static host
    ${generalParamDict}    Create Dictionary    type    virtualHost    ipAddress    1.1.1.2/24    gatewayHost
    ...    myExternalHost
    ${linkLayerParamDict}    Create Dictionary    physicalInterface    3/1/0
    Host Create    myStaticVirtualHost    ${generalParamDict}    ${linkLayerParamDict}
    # dhcpv4 host
    ${generalParamDict}    Create Dictionary    type    virtualHost    ipAddressAssignmentType    dhcpv4
    ${linkLayerParamDict}    Create Dictionary    physicalInterface    3/1/0
    Host Create    myDhcpv4VirtualHost    ${generalParamDict}    ${linkLayerParamDict}
    # tagged pppoe host
    ${generalParamDict}    Create Dictionary    type    virtualHost    ipAddressAssignmentType    pppoe-ipv4cp
    ${vlanIdList}    create List    100    200
    ${vlanPrioList}    create List    3
    ${linkLayerParamDict}    Create Dictionary    physicalInterface    3/1/0    vlanIdList    ${vlanIdList}    linkLayer
    ...    multipleTaggedVlan    vlanPrioList    ${vlanPrioList}
    ${pppoeParamDict}    Create Dictionary    username    test    password    test    isPapSupported
    ...    true
    Host Create    myPppoeVirtualHost    ${generalParamDict}    ${linkLayerParamDict}    ${EMPTY}    ${pppoeParamDict}
    # scaled static host
    ${generalParamDict}    Create Dictionary    type    virtualHost    ipAddress    1.1.1.2/24    gatewayHost
    ...    myExternalHost    numberOfHosts    5
    ${vlanIdList}    create List    7
    ${linkLayerParamDict}    Create Dictionary    physicalInterface    3/1/0    vlanIdList    ${vlanIdList}    linkLayer
    ...    taggedVlan    vlanPrioList    ${vlanPrioList}
    Host Create    myScaledStaticVirtualHost    ${generalParamDict}    ${linkLayerParamDict}
    Test Group Upload

taggedHost
    Test Group Create    ${TEST_NAME}
    # external host
    ${generalParamDict}    Create Dictionary    type    externalHost    ipAddress    1.1.1.1/24
    Host Create    myExternalHost    ${generalParamDict}    ${None}
    # static host 1
    ${generalParamDict}    Create Dictionary    type    virtualHost    ipAddress    1.1.1.2/24    gatewayHost
    ...    myExternalHost
    ${vlanIdList}    create List    100    200
    ${vlanPrioList}    create List    3
    ${linkLayerParamDict}    Create Dictionary    physicalInterface    3/1/0    vlanIdList    ${vlanIdList}    linkLayer
    ...    doubleTaggedVlan    vlanPrioList    ${vlanPrioList}
    Host Create    myStaticVirtualHost1    ${generalParamDict}    ${linkLayerParamDict}
    # static host 2
    ${generalParamDict}    Create Dictionary    type    virtualHost    ipAddress    1.1.1.3/24    gatewayHost
    ...    myExternalHost
    ${vlanIdList}    create List    100    200
    ${vlanPrioList}    create List    3
    ${linkLayerParamDict}    Create Dictionary    physicalInterface    3/1/0    vlanIdList    ${vlanIdList}    linkLayer
    ...    doubleTaggedVlan    vlanPrioList    ${vlanPrioList}
    Host Create    myStaticVirtualHost2    ${generalParamDict}    ${linkLayerParamDict}
    Test Group Upload
    ${debugDict}    debug Files Get
    Log Dictionary    ${debugDict}

taggedHostScaled
    Test Group Create    ${TEST_NAME}
    Comment    # external host
    Comment    ${generalParamDict}    Create Dictionary    type    externalHost    ipAddress    1.1.1.1/24
    Comment    Host Create    myExternalHost    ${generalParamDict}
    # static host
    ${generalParamDict}    Create Dictionary    type    virtualHost    ipAddressAssignmentType    dhcpv4    numberOfHosts
    ...    3
    ${vlanIdList}    create List    100,1,1    200    300
    ${vlanPrioList}    create List    3    4
    ${linkLayerParamDict}    Create Dictionary    physicalInterface    3/1/0    vlanIdList    ${vlanIdList}    linkLayer
    ...    multipleTaggedVlan    vlanPrioList    ${vlanPrioList}
    Host Create    myStaticVirtualHost    ${generalParamDict}    ${linkLayerParamDict}
    Test Group Upload

aggreateGroup
    Test Group Create    ${TEST_NAME}
    # create aggregate group
    ${aggregateGroupName}    Set Variable    myAggregateGroup
    ${aggregate1}    Create Dictionary    type    Host    fineStats    true    normalStats
    ...    true
    ${aggregate2}    Create Dictionary    type    AllClient    fineStats    true    normalStats
    ...    true
    ${aggregateList}    Create List    ${aggregate1}    ${aggregate2}
    ${aggregateGroupDict}    Create Dictionary    description    test123    aggregates    ${aggregateList}
    Aggregate Group Create    ${aggregateGroupName}    ${aggregateGroupDict}
    # external host
    ${generalParamDict}    Create Dictionary    type    externalHost    ipAddress    1.1.1.1/24
    Host Create    myExternalHost    ${generalParamDict}
    # static host
    ${generalParamDict}    Create Dictionary    type    virtualHost    ipAddress    1.1.1.2/24    gatewayHost
    ...    myExternalHost
    ${linkLayerParamDict}    Create Dictionary    physicalInterface    3/1/0
    ${statisticsDict}    Create Dictionary    aggregateGroup    ${aggregateGroupName}
    Host Create    myStaticVirtualHost    ${generalParamDict}    ${linkLayerParamDict}    ${EMPTY}    ${EMPTY}    ${statisticsDict}
    # upload to tvm-c
    Test Group Upload

propabilityDistributionProfile
    Test Group Create    ${TEST_NAME}
    # configure test group
    Probability Distribution Create    myProfile    10:1-5    40:20    50:30-50    description=funzt
    # upload to tvm-c
    Test Group Upload

cardLevelConfiguration
    Test Group Create    ${TEST_NAME}
    ${voipCallAttemptsRateLimit}    Create Dictionary    rampUpPeriodMetric    mins
    ${cardLevelConfigDict}    Create Dictionary    voipCallAttemptsRateLimit    ${voipCallAttemptsRateLimit}    dhcpDiscoverSetBroadcastFlag    true    dhcpRequestSetBroadcastFlag
    ...    true    outerVlanProtocolTag    88a8
    Card Level Configuration Create    3/1/0    ${cardLevelConfigDict}
    Test Group Upload

http
    Test Group Create    ${TEST_NAME}
    # external host
    ${paramDict}    Create Dictionary    type    externalHost    ipAddress    1.1.1.1/24
    Host Create    myExternalHost    ${paramDict}
    # http
    ${proxyDict}    Create Dictionary    host    myExternalHost
    Http External Proxy Create    myExternalHttpProxy    ${proxyDict}
    Http External Server Create    myExternalHttpServer    ${proxyDict}
    ${reqListItem1}    Create Dictionary    uri    bla
    ${reqListDict}    Create List    ${reqListItem1}
    ${httpReqListDict}    Create Dictionary    requestList    ${reqListDict}
    Http Request List Create    bla    ${httpReqListDict}
    # do it
    Test Group Upload

igmp
    Test Group Create    ${TEST_NAME}
    # host
    ${vlanIdList}    Create List    100    200
    ${hostParams}    Create Dictionary    ipAddressAssignmentType    dhcpv4    physicalInterface    3/1/0    vlanIdList
    ...    ${vlanIdList}    linkLayer    multipleTaggedVlan
    Host Create    myHost    ${hostParams}
    # igmp mc group list
    ${mcGroup1}    Create Dictionary    address    224.0.0.1    srcPort    900    dstPort
    ...    901
    ${mcGroup2}    Create Dictionary    address    225.0.0.1    srcPort    800    dstPort
    ...    801
    ${mcGroup3}    Create Dictionary    address    226.0.0.1    srcPort    700    dstPort
    ...    701
    ${mcGroupList}    Create List    ${mcGroup1}    ${mcGroup2}    ${mcGroup3}
    ${paramDict}    Create Dictionary    description    yay    mcGroupList    ${mcGroupList}
    Igmp Group List Create    myIgmpGroupList    ${paramDict}
    # igmp filter list
    ${filterList}    Create List    1.1.1.1    1.1.1.2    1.1.1.3    1.1.1.4
    ${paramDict}    Create Dictionary    description    yay    ipAddressList    ${filterList}
    Igmp Filter List Create    myIgmpFilterList    ${paramDict}
    # igmp app
    ${paramDict}    Create Dictionary    host    myHost    groupList    myIgmpGroupList
    Igmp Client Create    myIgmpApp    ${paramDict}
    # do it
    Test Group Upload
