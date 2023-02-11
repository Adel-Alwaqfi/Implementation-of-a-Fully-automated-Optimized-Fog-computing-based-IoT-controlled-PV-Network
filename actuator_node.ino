#include <RF24.h>
#include <RF24Network.h>
#include "printf.h"

//We have four possible lines to drive the loads (a line from each source to each load) S is for source L is for load,
//Each line have two relays to close or open the (Line and neutral) when needed at the same time

#define S1L1 2  //r1,r2
#define S2L1 3  //r3,r4
#define S1L2 4  //r5,r6
#define S2L2 5  //r7,r8

RF24 radio(9,10);                  // nRF24L01(+) radio attached using Getting Started board 

RF24Network network(radio);       // Network uses that radio
const uint16_t this_node = 04;    // Address of our node in Octal format ( 04,031, etc)
const uint16_t other_node = 00;   // Address of the other node in Octal format

const unsigned long interval = 5000; //ms  // How often to send 'hello world to the other unit

unsigned long last_sent;             // When did we last send?
unsigned long packets_sent;          // How many have we sent already


struct payload_t {                  // Structure of our payload
 float s1l1;
 float s2l1;
 float s1l2;
 float s2l2;
};

/**** Create a large array for data to be received ****
* MAX_PAYLOAD_SIZE is defined in RF24Network_config.h
* Payload sizes of ~1-2 KBytes or more are practical when radio conditions are good
*/
uint8_t dataBuffer[MAX_PAYLOAD_SIZE]; //MAX_PAYLOAD_SIZE is defined in RF24Network_config.h

void setup() {
  // put your setup code here, to run once:

  Serial.begin(115200);
  
  pinMode(S1L1, OUTPUT);
  pinMode(S2L1, OUTPUT);
  pinMode(S1L2, OUTPUT);
  pinMode(S2L2, OUTPUT);

  //Most likely the relay is active high
  digitalWrite(S1L1, LOW);
  digitalWrite(S2L1,LOW);
  digitalWrite(S1L2, LOW);
  digitalWrite(S2L2, LOW);

  radio.begin();
  radio.setPALevel(0);
  radio.setDataRate(2);
  network.begin(/*channel*/ 108, /*node address*/ this_node);
  
  Serial.print("Node started "); Serial.println(this_node); 
  
}

void loop() {
  // put your main code here, to run repeatedly: 

  network.update();                          // Check the network regularly
  
  unsigned long now = millis();              // If it's time to send a message, send it!
  if ( now - last_sent >= interval  )
  {
    last_sent = now;

    
    float s1l1 = digitalRead(S1L1);
    float s2l1 = digitalRead(S2L1);
    float s1l2 = digitalRead(S1L2);
    float s2l2 = digitalRead(S2L2);

    Serial.print("S1L1: "); Serial.println(s1l1);
    Serial.print("S2L1: "); Serial.println(s2l1);
    Serial.print("S1L2: "); Serial.println(s1l2);
    Serial.print("S2L2: "); Serial.println(s2l2);

    Serial.print("Sending...");
    payload_t payload = { s1l1, s2l1, s1l2, s2l2};
    RF24NetworkHeader header(/*to node*/ other_node);
    bool ok = network.write(header,&payload,sizeof(payload));
    if (ok)
      Serial.println("ok.");
    else
      Serial.println("failed.");
  }

  network.update();                   // Check the network regularly

  while ( network.available() ) {     // Is there anything ready for us?
    
    RF24NetworkHeader header;                          // If so, grab it and print it out
    uint16_t payloadSize = network.peek(header);       // Use peek() to get the size of the payload
    network.read(header,&dataBuffer,payloadSize);      // Get the data
    Serial.print("Received packet of size ");            // Print info about received data
    Serial.println(payloadSize);

    // Uncomment below to print the entire payload
    String command;
    for(uint32_t i=0;i<payloadSize;i++){
      Serial.print(char(dataBuffer[i]));
      command+= char(dataBuffer[i]);
      if(i%50 == 49){Serial.println();} //Add a line break every 50 characters
    } Serial.println();

    Serial.print("Command String: "); 
    Serial.println(command);

    //Excute command
    excute_command(command);    
  }
  
}

void excute_command(String command) {

  //Each scenario has its own command
  
  if(command == "0000"){

    reset_all_relays();
    
 
  }
  else if (command == "0001") {

      reset_all_relays();

      digitalWrite(S1L1, HIGH);
      
  }
  else if (command == "0010") {

    reset_all_relays();

      digitalWrite(S1L2, HIGH);
      
  }
  else if (command == "0100") {

    reset_all_relays();

      digitalWrite(S2L1, HIGH);
      
  }
  else if (command == "1000") {

    reset_all_relays();

      digitalWrite(S2L2, HIGH);
      
  }
  
}

void reset_all_relays() {

  digitalWrite(S1L1, LOW);
  digitalWrite(S2L1, LOW);
  digitalWrite(S1L2, LOW);
  digitalWrite(S2L2, LOW);

}