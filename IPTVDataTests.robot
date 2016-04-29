*** Settings ***
Library           ShenickCli.py    ${ip}    ${tgName}    ${usr}    ${partition}
Library           TrafficAnalysis.py
Library           Collections


*** Variables ***
${ip}             10.13.225.18
${tgName}         //GPON/GPON_Triple_Play_LoadTest
${usr}            IPTV
${partition}      2
${chassisType}    None


*** Test Cases ***
4P GPON_Data-Video_Test
    Comment    Test Case Defaults
    ${headEndMinMos}  ShenickCli.Get Head End Mos Statistic
    ${appList}     Create List  Client_HTTP_ONT16  Client_HTTP_ONT15  Client_HTTP_ONT14
    ${igmpDict}    Create Dictionary    csvFilePath=C:\\diversifEyeClient\\IPTV\\output\\Miscellaneous\\Summary_Multicast_Client.csv  qmVideoMOSLimit=${headEndMinMos}
    Set To Dictionary    ${igmpDict}    mosAppType    VQA
    Set To Dictionary    ${igmpDict}    zapAppType    STB_Client
    ${httpDict}    Create Dictionary    csvFilePath=C:\\diversifEyeClient\\IPTV\\output\\Miscellaneous\\Summary_HTTP_Client.csv
    Set To Dictionary    ${httpDict}    appType    HTTP
    Set To Dictionary    ${httpDict}    goodput    5000
    ${saveStatDict}    Create Dictionary    fileName=IPTV.zip
    ${copyDict}    Create Dictionary    serverIp=10.13.225.18
    Set To Dictionary    ${copyDict}    userName     cli
    Set To Dictionary    ${copyDict}    password     diversifEye
    Set To Dictionary    ${copyDict}    sourceFilePath     IPTV.zip
    Set To Dictionary    ${copyDict}    destFilePath     C:/diversifEyeClient/analysis/bin/IPTV.zip
    ShenickCli.Stop Test Group
    ShenickCli.Enable Disable Applications  ${appList}  Disabled
    Sleep    3
    ShenickCli.Enable Disable Applications  ${appList}  Enabled
    Sleep    3
    ShenickCli.Enable Disable Applications  all  Disabled
    Sleep    3
    ShenickCli.Enable Disable Applications  all  Enabled
    Sleep    3
    ShenickCli.Start Test Group
    Sleep    15
    ShenickCli.In Service Out Service Applications  ${appList}  Out of Service
    Sleep    3
    ShenickCli.In Service Out Service Applications  ${appList}  In Service
    Sleep    10
    ShenickCli.In Service Out Service Applications  all  Out of Service
    Sleep    3
    ShenickCli.In Service Out Service Applications  all  In Service
    ShenickCli.In Service Out Service Applications  ${appList}  In Service
    ShenickCli.Save Stats    ${saveStatDict}
    ShenickCli.Stop Test Group
    TrafficAnalysis.Copy File From Server    ${copyDict}
    TrafficAnalysis.Run Analysis Batch File    C:\\diversifEyeClient\\analysis\\bin\\IPTV.Zip    C:\\diversifEyeClient
    TrafficAnalysis.Evaluate Igmp Applications    ${igmpDict}
    TrafficAnalysis.Evaluate Http Applications    ${httpDict}


