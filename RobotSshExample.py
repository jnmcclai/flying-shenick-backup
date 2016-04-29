import sys
import Crypto
import paramiko.client as client
sys.modules['Crypto'] = Crypto

hostName = "10.13.254.40"
uName = "Pi"
pWord = "Raspberry"

client = client.SSHClient()
client.load_system_host_keys()
client.connect(hostname=hostName, port=22, username=uName, password=pWord)
response = client.exec_command('ls')

print response
