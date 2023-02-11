

import paho.mqtt.client as mqtt
import influxdb_client
import time
import datetime
import fnmatch


#influx things
bucket = "WiNS"
org = "HTU"
token = "7CT4atGOymHbAU2e8BuVMDml8Np-hcV1OBqesx1HMkeS75ZP3ST5fsgxNWm6SanmaTs26CPLd7DCJgyapUAYsg=="
# Store the URL of your InfluxDB instance
url="127.0.0.1:8086"

#create influxdb client
db_client = influxdb_client.InfluxDBClient(
   url=url,
   token=token,
   org=org
)


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):

     print("Connected to the Broker with result code "+str(rc))
    
   
# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("127.0.0.1", 1883, 60)
time.sleep(1)

#set the xsl initially to deafult (No loads connected)       
payload = "0000"
topic = "$command/HTU/HTU/WiNS LAB/gateway/WiNS LAB/Switches"
print("Starting with the xsl =", payload, "case")
print("Sending payload", payload, "to", topic)
client.publish(topic,payload)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_start()


while True:

   

    #Start S1
    payload = "0001"
    print("Changing to xsl =", payload, "case")
    print("Sending payload", payload, "to", topic)
    client.publish(topic,payload)

    Tdelay = 10
    print("The code will be sleeping for ", Tdelay, " seconds for data collection...")
    print("Time before: ", datetime.datetime.now())
    time.sleep(Tdelay)
    print("Time after: ", datetime.datetime.now())


    #Query the current readings and store them in an array 
    #Instantiate the query client.
    query_api = db_client.query_api()
            
    #Query the voltage last value to check it against the thresholds
    query = 'from(bucket: "WiNS") |> range(start: -5s) |> filter(fn: (r) => r["_measurement"] == "Inverter1") |> filter(fn: (r) => r["_field"] == "Battery_Current"  or r["_field"] == "Output_Current") |> aggregateWindow(every: 5s, fn: last, createEmpty: false) |> limit(n: 1) |> yield(name: "last")'

    print("Sending query ", query, "to db...")
    #get the results
    result = query_api.query(org=org, query=query)

    #print the results
    results = []
    for table in result:
        for record in table.records:
            results.append((record.get_field(), record.get_value()))

    print(results)

    if(len(results) == 0):
        print("No data returned from the query")
        continue

    I_battery = results[0][1]
    PV_voltage = results[1][1]

    print("Battery_Current: ", I_battery)
    print("Ouptut_Current: ", PV_voltage)
            
    #Compare with thresholds

    Tvoltage = 5
    Tcurrent = 5

    print("Comparing values to preset thresholds...")
            
    while(PV_voltage <= Tvoltage or I_battery <= Tcurrent):

        print("Nothing to do...");

        Tdelay = 10
        print("The code will be sleeping for ", Tdelay, " seconds for data collection...")
        print("Time before: ", datetime.datetime.now())
        time.sleep(Tdelay)
        print("Time after: ", datetime.datetime.now())

        #Query the voltage last value to check it against the thresholds
        query = 'from(bucket: "WiNS") |> range(start: -5s) |> filter(fn: (r) => r["_measurement"] == "Inverter1") |> filter(fn: (r) => r["_field"] == "Battery_Current"  or r["_field"] == "Output_Current") |> aggregateWindow(every: 5s, fn: last, createEmpty: false) |> limit(n: 1) |> yield(name: "last")'

        print("Sending query ", query, "to db...")
        #get the results
        result = query_api.query(org=org, query=query)

        #print the results
        results = []
        for table in result:
            for record in table.records:
                results.append((record.get_field(), record.get_value()))

        print(results)

        if(len(results) == 0):
            print("No data returned from the query")
            continue

        I_battery = results[0][1]
        PV_voltage = results[1][1]

        print("Battery_Current: ", I_battery)
        print("Ouptut_Current: ", PV_voltage)

    else:

        payload = "0010"
        print("Changing to xsl =", payload, "case")
        print("Sending payload", payload, "to", topic)
        client.publish(topic,payload)

        Tvoltage = 5
        Tcurrent = 5

        #Reset values
        PV_voltage = 0
        I_battery = 0

        while(PV_voltage <= Tvoltage or I_battery <= Tcurrent):

            Tdelay = 10
            print("The code will be sleeping for ", Tdelay, " seconds for data collection...")
            print("Time before: ", datetime.datetime.now())
            time.sleep(Tdelay)
            print("Time after: ", datetime.datetime.now())

            #get the values
            query = 'from(bucket: "WiNS") |> range(start: -5s) |> filter(fn: (r) => r["_measurement"] == "Inverter1") |> filter(fn: (r) => r["_field"] == "Battery_Current"  or r["_field"] == "Output_Current") |> aggregateWindow(every: 5s, fn: last, createEmpty: false) |> limit(n: 1) |> yield(name: "last")'

            print("Sending query ", query, "to db...")
            #get the results
            result = query_api.query(org=org, query=query)

            #print the results
            results = []
            for table in result:
                for record in table.records:
                    results.append((record.get_field(), record.get_value()))

            print(results)

            if(len(results) == 0):
                print("No data returned from the query")
                continue

            I_battery = results[0][1]
            PV_voltage = results[1][1]

            print("Battery_Current: ", I_battery)
            print("Output_Current: ", PV_voltage)
        
        else:

            continue;
            
           
           











