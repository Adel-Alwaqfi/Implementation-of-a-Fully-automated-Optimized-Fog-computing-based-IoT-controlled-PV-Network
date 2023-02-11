import subprocess
import sys
import os
import redis
import paho.mqtt.client as mqtt
import time
from datetime import datetime as dt
from struct import *
from RF24 import *
from RF24Network import *
import json

#start redis-server
import db

#Boot information
boot = dt.now()
print(f"\n\t\t*** Gateway (Edge Node) Started ***\n\t\t   @  {str(boot)}\n")

#get mac of gateway
import re,uuid 
MAC =':'.join(re.findall('..', '%012x' % uuid.getnode()))

#broker settings
broker_address = "put your ip here"
port = 1883
timeout = 10
provisioning_topic = f"$provisioning/{MAC}" #This topic is used to provision, unprovision, and edit gateway
provisioning_connected_topic = f"$connected/{MAC}/provisioning" #This topic is used to publish connectivity status
gateway_connected_topic = f"$connected/{MAC}/gateway"  #this is used after the provisioning has happened
time.sleep(0.5)

print("\t\t\t\tBroker Settings:\n\t\t-------------------------------------------\n")
print(f"Broker Address: {broker_address}\nPort: {port}\nConnection Timeout: {timeout}\nProvisioning Topic: {provisioning_topic}\n")

#callbacks of provisioning client
def provisioning_on_message(client, userdata, msg):
    
    print("*RECEIVED command from the Cloud:\n")
    print(f"topic:{msg.topic}\ncontent:{msg.payload.decode()}\n")
    
    payload = json.loads(msg.payload.decode())
    
    try:

        if(msg.topic == provisioning_topic):

            if(payload["command"] ==  "provision"):
            
                from provisioning import provision
                
                provisioning_info = payload['provisioning_info']
                provisioning_info_string = json.dumps(payload['provisioning_info'])
                
                response = provision(provisioning_info_string)
                
                if(response == 0):
                    
                    topic = f"{provisioning_topic}/{payload['provisioning_info']['main_id']}"
                    payload = json.dumps({"provisioned":True, "provisioning_info":provisioning_info})

                    print("informing the cloud of the provisioning state>>>\n")
                    print(f"pub to topic:\n{topic}\n payload:\n{payload}")
                    r, mid = client.publish(topic, payload, qos=2)

                    while (r != 0):

                        print("Failed to inform cloud. Retrying...")
                        print("informing the cloud of the provisioning state>>>\n")
                        print(f"pub to topic:\n{topic}\n payload:\n{payload}")
                        r, mid = client.publish(topic, payload, qos=2)

                    else:

                        print(f"\nreturn code: {r} **Done provisioning and informing cloud**\n")
                        global provisioned
                        provisioned = True

                elif(response == 1):
                    
                    topic = f"{provisioning_topic}/{payload['provisioning_info']['main_id']}"
                    payload = json.dumps({"provisioned":False, "reason":"redis failure"})

                    print("informing the cloud of the provisioning state>>>\n")
                    print(f"pub to topic:\n{topic}\n payload:\n{payload}")
                    r, mid = client.publish(topic, payload, qos=2)

                    while (r != 0):

                        print("Failed to inform cloud. Retrying...")
                        print("informing the cloud of the provisioning state>>>\n")
                        print(f"pub to topic:\n{topic}\n payload:\n{payload}")
                        r, mid = client.publish(topic, payload, qos=2)
  
                    else:

                        print(f"\nreturn code: {r} **Failed provisioning and cloud is informed**\n")

                else: 
                    
                    topic = f"{provisioning_topic}/{payload['provisioning_info']['main_id']}"
                    payload = json.dumps({"provisioned":False, "reason":"unknown"})

                    print("informing the cloud of the provisioning state>>>\n")
                    print(f"pub to topic:\n{topic}\n payload:\n{payload}")
                    r, mid = client.publish(topic, payload, qos=2)

                    while (r != 0):

                        print("Failed to inform cloud. Retrying...")
                        print("informing the cloud of the provisioning state>>>\n")
                        print(f"pub to topic:\n{topic}\n payload:\n{payload}")
                        r, mid = client.publish(topic, payload, qos=2)
  
                    else:
                        
                        print(f"\nreturn code: {r} **Failed provisioning and cloud is informed**\n")
                
            elif(payload['command'] == "unprovision"):

                print("Can't unprovision an unprovisioned gateway!\n")
                
                topic = provisioning_topic
                payload = json.dumps({"unprovisioned":False, "reason":"not provisioned yet"})

                print("informing the cloud of the provisioning state>>>\n")
                print(f"pub to topic:\n{topic}\n payload:\n{payload}")
                r, mid = client.publish(topic, payload, qos=2)

                while (r != 0):

                    print("Failed to inform cloud. Retrying...")
                    print("informing the cloud of the provisioning state>>>\n")
                    print(f"pub to topic:\n{topic}\n payload:\n{payload}")
                    r, mid = client.publish(topic, payload, qos=2)
                
                else:

                    print(f"\nreturn code: {r} **Failed unprovisioning and cloud is informed**\n")

    except:
        
        print("Topic or command key does not exist.")
            
#on_connect callback        
def provisioning_on_connect(client, userdata, flags, rc):
   
    if rc == 0:

        connected = True
        
        print("<Provisioning> client has been connected to the broker.\n")
        
        print(f"Subscribing to topic {provisioning_topic}...")
        response, mid = client.subscribe(provisioning_topic,2)
        
        if (response == 0):
                print("Subscribed.\n")

        #Inform the broker about the connection, this is for tracking clients activity status
        client.publish(f"{provisioning_connected_topic}/$status",json.dumps({"connected":True}), qos=2)

    else:

        print("Couldn't connect to broker.\n")
        
        if(rc == 1):

            print(f"Return Code: {rc}, Connection refused - incorrect protocol version\n")

        elif(rc == 2):

            print(f"Return Code: {rc}, Connection refused - invalid client identifier\n")

        elif(rc == 3):

            print(f"Return Code: {rc}, Connection refused - server unavailable\n")
        
        elif(rc == 4):

            print(f"Return Code: {rc}, Connection refused - bad username or password\n")
        
        elif(rc == 5):

            print(f"Return Code: {rc}, Connection refused - not authorized. Make sure to set username and password\n")
            
def provisioning_on_disconnect(client, userdata, rc):
    
    if rc == 0:

        print("<Provisioning> client disconnected from broker.\n")
        client.publish(f"{provisioning_connected_topic}/$status",json.dumps({"connected":False}), qos=2)

#Get provisioning state from redis
n = 0 #the first database
r = redis.Redis(db=n)

#Get the state of provisioning
if(r):
    
    is_provisioned = r.get("is_provisioned")
    
    if(is_provisioned == None):
        
        print("The gateway needs provisioning.\n")
        
        global provisioned
        provisioned = False
        
        n = 1 #the second db for secrets
        r = redis.Redis(db=n)

        #Configure and start the MQTT provisioning client
        provisioning_client = mqtt.Client(clean_session=True)
        provisioning_client.on_message=provisioning_on_message
        provisioning_client.on_connect=provisioning_on_connect
        provisioning_client.on_disconnect=provisioning_on_disconnect

        try:
            
            print(f"\n*Attempting Connection to MQTT Broker|Timeout: {timeout} s...")
            global connected
            connected = False
            provisioning_client.connect(broker_address,port,timeout) #connect to broker
            provisioning_client.loop_start()  #It puts the client loop on another thread and continues whatever else in the main thread
            
        except Exception as e:
            
            print(f"\nException raised: {e}\n")
            print("Restarting gateway in 3 seconds...")
            time.sleep(3)
           
            #restart the script
            python = sys.executable
            os.execl(python, python, * sys.argv)


        while (not provisioned):
            
            print("Waiting for provisioning payload from cloud", flush=True, end='\r')
            time.sleep(1)
            print('                                           ', flush=True, end='\r')
            time.sleep(1)
            
        else:
            
            print("Terminating the provisioning client connection...\n")
            provisioning_client.loop_stop()  
            provisioning_client.disconnect()                       
    else:
        
        provisioned = True
else:
    
    raise Exception("Couldn't Connect to Redis to get provisioning state.")

#get provisioning info
n = 0    
r = redis.Redis(db=n)
info = r.get("provisioning_info").decode()
info = json.loads(info)

#extract gateway properties
main_id = info['main_id']
mqtt_client_id = info['mqtt_client_id']
mqtt_username = info['mqtt_username']
mqtt_password = info['mqtt_password']
main_name = info['main_name']
section_name = info['section_name']
device_type = info['device_type']
device_name = info['device_name']
number_of_nodes = info['wsn']['number_of_nodes']
frequency_channel = info['wsn']['frequency_ch']
data_rate = info['wsn']['data_rate']
power_level = info['wsn']['power_level']
        
print("\t\tThis gateway is provisioned with the following:\n\t\t-------------------------------------------\n")
print(f"Main ID: {main_id}")
print(f"MQTT Client ID: {mqtt_client_id}")
print(f"MQTT Username: {mqtt_username}")
print(f"MQTT Password: {mqtt_password}")
print(f"Main Name: {main_name}")
print(f"Section Name: {section_name}")
print(f"Device Type: {device_type}")
print(f"Gateway Name: {device_name}")
print(f"Radio Configurations:->*Channel: {frequency_channel} *Data Rate: {data_rate} *Power Level: {power_level}")
print(f"\nNumber of Nodes in WSN: {number_of_nodes}")

#Extract nodes from WSN, each node is an object inside an array, so nodes is an array of objects
nodes = info['wsn']['nodes']
  
#print nodes' details, prepares command topics and WSN dict
command_topics = {}
#Add the gateway command topic
command_topics[f"$command/{main_id}/{main_name}/{section_name}/{device_type}/{device_name}"] = "gateway" 
WSN = {}      #{key: value, ...} ; //key is node address, value is node as an object
i = 1

for node in nodes:
    
    #associate command_topic with node_name
    command_topics[f"$command/{main_id}/{main_name}/{section_name}/{device_type}/{device_name}/{node['name']}"] = node['name']
  
    #associate node_address with node object (dict)
    WSN[node['address']] =  node
    
    print(f"node_{i}: *Address: {node['address']} *Name: {node['name']} *Number of Values: {len(node['values'])}")

    i+=1

    #Extract values of each node, each value is an object inside an array, so values is an array of objects
    values = node['values']

    j = 1
    for value in values:
        print(f"\tvalue_{j}: *Name: {value['name']} *Type: {value['type']} *Unit: {value['unit']}")
        j+=1 
    
        
    
print("\nIf you would like to un-provision the gateway with other settings,\nplease use the cloud interface to initiate the process :)\n")
    
#View topics used for receiving commands
print("\n*Viewing command topics...\n")

print("Command topics: \n")
for command_topic in command_topics.keys():
    print(command_topic)

#callbacks of gateway client
def gateway_on_connect(client, userdata, flags, rc):
    
    if rc == 0:
        
        print("<Gateway> client connected successfully.\n")

        #Clear retained message about disconnection
        client.publish(f'{gateway_connected_topic}/$status',qos=2,retain=True)

        #Inform the broker about the connection, this is for tracking clients activity status
        client.publish(f"{gateway_connected_topic}/$status",json.dumps({"connected":True}), qos=2)
        
        #subscribe to provisioning topic
        print(f"Subscribing to topic {provisioning_topic}...\n")
        response, mid = client.subscribe(provisioning_topic,2)
        
        if (response == 0):
                print("Subscribed.\n")

        #subscribe to connected topic
        print(f"Subscribing to topic {gateway_connected_topic}...")
        response, mid = client.subscribe(gateway_connected_topic,2)
        
        if (response == 0):
                print("Subscribed.\n")

        #subscribe to command topics, as a single topic
        topic = f"$command/{main_id}/{main_name}/{section_name}/{device_type}/{device_name}/#"
        print(f"Subscribing to topic {topic}...\n")
        response, mid = client.subscribe(topic,2)
        if (response == 0):
            print("Subscribed.\n")

    else:

        print("Couldn't connect to broker.\n")
        
        if(rc == 1):

            print(f"Return Code: {rc}, Connection refused - incorrect protocol version\n")

        elif(rc == 2):

            print(f"Return Code: {rc}, Connection refused - invalid client identifier\n")

        elif(rc == 3):

            print(f"Return Code: {rc}, Connection refused - server unavailable\n")
        
        elif(rc == 4):

            print(f"Return Code: {rc}, Connection refused - bad username or password\n")
        
        elif(rc == 5):

            print(f"Return Code: {rc}, Connection refused - not authorised. Make sure to set username and password\n")

def gateway_on_disconnect(client, userdata, rc):
    
    if rc == 0:

        print("<Gateway> client disconnected from broker.\n")
        
#on message callback for the commands
def gateway_on_message(client, userdata, msg):
   
    print("*Received command from the Cloud:\n")
    print(f"topic:{msg.topic}\ncontent:{msg.payload.decode()}\n")

    #Reroute the command based on its topic
    if(msg.topic == provisioning_topic):
        
        #Get provisioning state from redis
        n = 0 #the first database
        db = redis.Redis(db=n)
        
        command = json.loads(msg.payload.decode())['command']
        
        #Reroute the command based on its type
        if(command == "provision"):
            
            #Get the state of provisioning
            is_provisioned = db.get("is_provisioned")

            decoded = is_provisioned.decode()
            print(f"is_provisioned? {decoded}\n")

            if(decoded == "true"):
                
                print("Gateway is already provisioned!\n")
                
                topic = f'{provisioning_topic}/{main_id}'
                payload = json.dumps({"provisioned":False, "already_to_id":main_id})

                print("informing the cloud of the provisioning state>>>\n")
                print(f"pub to topic:\n{topic}\n payload:\n{payload}")
                r, mid = client.publish(topic, payload, qos=2)
    
                while(r != 0):

                    print("\nFailed to inform cloud. Retrying...\n")
                    print(f"pub to topic:\n{topic}\n payload:\n{payload}")
                    r, mid = client.publish(topic, payload, qos=2)
                
                else:

                    print("\nCloud informed.\n")
        
        elif(command == "unprovision"):
        
            from unprovisioning import unprovision

            r = unprovision()

            if(r == 0):

                print("\nUnprovisioned Successfully.\n")

                payload = json.dumps({"unprovisioned":True, "from_id":main_id})
                
                print("informing the cloud of the unprovisioning state>>>\n")
                print("pub to topic:")
                print(f"{provisioning_topic}\n payload:\n{payload}\n")
                r, mid = client.publish(provisioning_topic, payload, qos=2)

                while(r != 0):

                    print("\nFailed to inform cloud. Retrying...\n")
                    print("pub to topic:")
                    print(f"{provisioning_topic}\n payload:\n{payload}\n")
                    r, mid = client.publish(provisioning_topic, payload, qos=2)

                else:
                
                    print("\nCloud informed.\n")
                    global restart
                    restart = True
            
            else:

                print("Unprovisioning failed.\n")
                
                topic = f'{provisioning_topic}/{main_id}'
                payload = json.dumps({"unprovisioned":False, "from_id":main_id, "reason":"redis failure"})
                
                print("informing the cloud of the unprovisioning state>>>\n")
                print("pub to topic:")
                print(f"{provisioning_topic}\n payload:\n{payload}\n")
                r, mid = client.publish(topic, payload, qos=2)

                while(r != 0):

                    print("\nFailed to inform cloud. Retrying...\n")
                    print("pub to topic:")
                    print(f"{provisioning_topic}\n payload:\n{payload}\n")
                    r, mid = client.publish(provisioning_topic, payload, qos=2)

                else:
                
                    print("\nCloud informed.\n")
                
        else:
            
            print("It is a node-type command.\n")

            send_to_node(msg.topic, msg.payload)

gateway_client = mqtt.Client(clean_session=True)
print(f"\n*Attempting Connection to MQTT Broker|Timeout: {timeout} s...")
gateway_client.on_connect=gateway_on_connect
gateway_client.on_disconnect=gateway_on_disconnect
gateway_client.on_message=gateway_on_message
gateway_client.will_set(f'{gateway_connected_topic}/$status',json.dumps({"connected":False}), qos=2, retain=True) #Set the last will message in case of client unexpected disconnection

try:

    gateway_client.connect(broker_address,port,timeout) #connect to broker

except Exception as e:

    print(f"\nException raised: {e}\n")
    print("Restarting gateway in 3 seconds...")
    time.sleep(3)
    
    #restart the script
    python = sys.executable
    os.execl(python, python, * sys.argv)

gateway_client.loop_start()  #It puts the client loop on another thread and continues whatever else in the main thread

radio = RF24(22,0) # CE Pin, CSN Pin, SPI Speed
network = RF24Network(radio)

# Address of base node in Octal format (01, 021, etc)
octlit = lambda n:int(n, 8)
this_node = octlit("00")

#get the data rate of radio
data_rates = {0:RF24_250KBPS, 1:RF24_1MBPS, 2:RF24_2MBPS}
data_rate = data_rates[info['wsn']['data_rate']]

#get power level of radio
power_levels = {0:RF24_PA_MIN, 1:RF24_PA_LOW, 2:RF24_PA_HIGH, 3:RF24_PA_MAX}
power_level = power_levels[info['wsn']['power_level']]

#get the frequency channel
channel = info['wsn']['frequency_ch']

#Setup and Initialization
radio.begin()
time.sleep(0.1)
radio.setDataRate(data_rate)
time.sleep(0.1)
radio.setPALevel(power_level)
time.sleep(0.1)
network.begin(channel, this_node)
time.sleep(0.1)
print(f"\n\t\t\t\t*** RADIO DETAILS ***\n")
radio.printDetails()
print()
            

#radio functions
def send_to_node(topic, payload):

    print("Retrieving node from topic...")
    target_node = command_topics[topic]
    print("Node:", target_node)

    print("Retrieving address from node...")
    target_address = ""
    for address, node in WSN.items():
        if node['name'] == target_node:
            target_address = address

    print(f"Address: {target_address}")

    target_address = octlit(target_address)

    network.update()
    print(f"Sending command to node {target_address}")
    ok = network.write(RF24NetworkHeader(target_address), payload)

    if ok:
        print("Command Sent Successfully.\n")
    else:
        print("Failed to send command!\nMake sure the node does exist and is powered up.\n")

def get_from_node():
    
    network.update()
    
    if network.available:
        
        while network.available():
            
            header = RF24NetworkHeader()
            payload_size = network.peek(header)
            header, payload = network.read(payload_size)  # read(buffer length)
            
            global dt
            node_address = "0" + str(header.from_node)    #padding the address with zero     
            print(f"\n*DATA RECEIVED* @ {dt.now()}")
            print(f"From node: {node_address}")
                
            print(f"Payload Size: {payload_size}")
            num_of_values = int(payload_size/4)
            
            #drop payloads that are multiples of 4
            if payload_size % 4 != 0:
                print("Payload size is not accepted. Send only floats.")
                continue
                
            received = unpack('<'+'f'*num_of_values,bytes(payload))
            print(f"Data: {received}")

            #check whether this node is provisioned on the cloud:
            if node_address in WSN.keys():
                
                node = WSN[node_address]
                print(f"Address maps to provisioned node: {node['name']}")
                #get its info
                expected_num_of_values = len(node['values'])
                
                if(expected_num_of_values == num_of_values):
                    
                    #get their names and types and preapre json string
                    output_payload = {}
                    i = 0
                    for v in received:
                        value = node['values'][i]
                        name = value['name']
                        its_type = value['type']
                        
                        #cast the value to its type
                        if(its_type == 'float'):
                            output_payload[name] = float(v)
                        if(its_type == 'int'):
                            output_payload[name] = int(v)
                        if(its_type == 'bool'):
                            output_payload[name] = bool(v)
                        
                        i+=1
                        
                    print(f"output_payload: {output_payload}")
                    
                    send_to_cloud(json.dumps(output_payload), node)
                    time.sleep(0.2)
                    
                else:
                    
                    print(f"Received {num_of_values} values, expected {expected_num_of_values}. Fix provisioning from the cloud.")
                         
            else:
               
                print(f"Node {node_address} is not provisioned from the cloud. Provision it and try again.\n")
            
    else:

        print("Radio is not available :(\n")

def send_to_cloud(payload, node): #add other arguments if needed
     
    print("Sending to MQTT BROKER...\n")

    topic = f"$STATE/{main_id}/{main_name}/{section_name}/{device_type}/{device_name}/{node['name']}"
    
    node_address = node['address']
    
    print(f"From node {node_address} using topic: {topic} \n")

    r, mid = gateway_client.publish(topic, payload, 2) #topic, payload, QoS, retained

    while(r !=0):
        print("*Something went wrong. Retrying...\n")
        r, mid = gateway_client.publish(topic, payload, 2)
    else:
        print("Payload was sent successfully.\n")
        
restart = False

while(not restart):

    get_from_node()
    time.sleep(0.5)

else:
    
    print("\nInforming the cloud, disconnecting the <Gateway> MQTT client, and restarting the gateway...\n")

    r, mid = gateway_client.publish(f"{gateway_connected_topic}/$status",json.dumps({"connected":False}), qos=2)

    while(r != 0):
        
        print("\nFailed to inform cloud. Retrying...")
        r, mid = gateway_client.publish(f"{gateway_connected_topic}/$status",json.dumps({"connected":False}), qos=2)
    
    else:
        
        s = 3
        print(f"\nCloud Informed.\nRestarting gateway in {i} seconds...\n")
        gateway_client.loop_stop()
        gateway_client.disconnect()
        
        for i in range(0,s):
            time.sleep(1)
            print(f"\n{i+1}")

        #restart the script
        python = sys.executable
        os.execl(python, python, * sys.argv)