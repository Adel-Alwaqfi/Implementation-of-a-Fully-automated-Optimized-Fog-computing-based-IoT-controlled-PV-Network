/*
 This is the code of the first SA node at address 01
 It sends its state and then checks the channel periodically 
 for incoming payloads from the gateway that's working at address 00
 */

#include <RF24Network.h>
#include <RF24.h>
#include <SPI.h>


#define vDCbatteryPin A0
#define vDCPVPin A1
#define vRMSPin A2
#define iRMSPin A3
#define iDCbatteryPin A4
#define iDCPVPin A5


RF24 radio(7,8);                    
RF24Network network(radio);          // Network uses that radio

const uint16_t this_node = 02;        // Address of our node in Octal format
const uint16_t other_node = 00;       // Address of the other node in Octal format

const unsigned long interval = 5000; // How often to send the SA node state  // <----------EDIT------------ */
unsigned long last_sent;             // When did we last send?


//Structure for the transmitted payloads
struct payload_t {  float dataOut[6];  };



/*Globals*/
float refVoltage = 5.06;  //Supplied by the regulator (as measured)         // <----------EDIT------------ */
float v1; //V_DC_battery
float v2; //V_DC_PV
float v3; //V_AC_Inverter

float v4; //A_AC_Inverter
float v5; //A_DC_Battery
float v6; //A_DC_PV

const int mVperAmp = 66; // use 185 for 5A Module, and 66 for 30A Module
float Vref  = 0; //read your Vcc voltage,typical voltage should be 5000mV(5.0V)

void setup(void)
{
  //Begin the serial comm.
  Serial.begin(9600);
  Serial.print("*SA node of address ");
  Serial.print(this_node);
  Serial.println("*");

  // Use external voltage reference
   //analogReference(EXTERNAL);

   Vref = readVref(); //read the reference votage(default:VCC)

  //Begin SPI class, radio, and network objects
  SPI.begin();
  radio.begin();
  radio.setDataRate(2); //set datarate to 250 Kbps
  radio.setPALevel(3); //set power level to max
  network.begin(108, this_node);  //provide channel (1 ,125), and this address node in octal 
}


void loop() {

  unsigned long now = millis();              // If it's time to send a message, send it!
  
  if ( now - last_sent >= interval  )
  {
     last_sent = now;

     V_DC();    //Battery & PV
     V_RMS();  //Load Voltage
     I_RMS(); //Load Current
     I_DC();  //Battery & PV
     send_radio();
     Serial.println("---------------------------------");
          
  }  
}


void send_radio() {

    //Send sensors' readings
    network.update();                          // Check the network regularly
    Serial.print("Sending...");
    
    payload_t payload = { {v1,v2,v3,v4,v5,v6} };
    RF24NetworkHeader header(/*to node*/ other_node);
    bool ok = network.write(header,&payload,sizeof(payload));
    if (ok)
      Serial.println("ok.");
    else
      Serial.println("failed.");

}

void V_DC() {
    
   //Read the Analog Input
   v1 = analogRead(vDCbatteryPin);  //battery
   v2 = analogRead(vDCPVPin);       //PV

   //For sensor 1 (Battery)
  float f1 = 20.5;       //calculated to get (55V maximum), measured, and calibrated f = (r1+r2)/r1    r2= 50, r1= 5  // <----------EDIT------------ */

  //For sensor 2 (PV)
  float f2 = 20.5;   //calculated to get (55V maximum), measured, and calibrated f = (r1+r2)/r1    r2= 100, r1= 5  // <----------EDIT------------ */

    
   //Determine voltage at ADC input
   v1  = (v1* refVoltage) / 1023.0; 
   v2  = (v2 * refVoltage) / 1023.0;
   
   // Calculate voltage at divider input
   v1 = v1 * f1; 
   v2 = v2 * f2;

   // Print results to Serial Monitor to 2 decimal places
    Serial.print("V_Battery: "); Serial.print(v1, 2); Serial.println(" VDC.");
    Serial.print("V_PV     : "); Serial.print(v2, 2); Serial.println(" VDC.");
}  

void V_RMS() {

  int numSamples = 5000;                                                  // <----------EDIT------------ */
  int numTurns = 400; //by trial and error for the transformer
  const float offset = 2.528;                                             // <----------EDIT------------ */
  double sum = 0;
  
   // Take a number of samples and calculate RMS voltage
    for ( int i = 0; i < numSamples; i++ ) {
        
        // Read ADC, convert to voltage, remove offset
        v3 = analogRead(vRMSPin);
        v3 = (v3 * refVoltage) / 1023.0;
        v3 = v3 - offset;
        
        // Calculate the sensed voltage
        v3 = v3 * numTurns;
        
        // Square value and add to sum
        sum += pow(v3, 2);
    }
    
    v3 = sqrt(sum / numSamples);
     
    Serial.print("V_output : "); Serial.print(v3, 2); Serial.println(" VRMS.");    
}

void I_RMS() {


    v4 = readACCurrent(iRMSPin);
     
    Serial.print("I_output : "); Serial.print(v4, 2); Serial.println(" ARMS.");  
}

void I_DC() {

    float sum = 0;
    int counts = 10;
    
    for (int i = 0; i < counts; i++) {
    
      sum+= readDCCurrent(iDCbatteryPin);
    }

    v5 = sum/counts;

    
    v6 = - readDCCurrent(iDCPVPin);

    
    Serial.print("I_Battery: "); Serial.print(v5, 2); Serial.println(" ADC."); 
    Serial.print("I_PV     : "); Serial.print(v6, 2); Serial.println(" ADC.");

}

/*read DC Current Value*/
float readDCCurrent(int Pin)
{
    int analogValueArray[31];
    for(int index=0;index<31;index++ )
    {
      analogValueArray[index]=analogRead(Pin);
    }
    int i,j,tempValue;
    for (j = 0; j < 31 - 1; j++  )
    {
        for (i = 0; i < 31 - 1 - j; i++  )
        {
            if (analogValueArray[i] > analogValueArray[i - 1])
            {
                tempValue = analogValueArray[i];
                analogValueArray[i] = analogValueArray[i - 1];
                analogValueArray[i - 1] = tempValue;
            }
        }
    }
    float medianValue = analogValueArray[(31 - 1) / 2];
    float DCCurrentValue = (medianValue / 1024.0 * Vref - Vref / 2.0) / mVperAmp;  //Sensitivity:100mV/A, 0A @ Vcc/2
    return DCCurrentValue;
}

/*read AC Current Value and ruturn the RMS*/
float readACCurrent(int Pin)
{
   int analogValue;             //analog value read from the sensor output pin
   int maxValue = 0;            // store max value
   int minValue = 1024;         // store min value
   unsigned long start_time = millis();
   while((millis()-start_time) < 200) //sample for 0.2s
   {
       analogValue = analogRead(Pin);
       if (analogValue > maxValue)
       {
           maxValue = analogValue;
       }
       if (analogValue < minValue)
       {
           minValue = analogValue;
       }
   }
   float Vpp = (maxValue - minValue) * Vref / 1024.0;
   float Vrms = Vpp / 2.0 * 0.707 / mVperAmp; //Vpp -> Vrms
   return Vrms;
}

/*read reference voltage*/
long readVref()
{
    long result;
#if defined(__AVR_ATmega168__) || defined(__AVR_ATmega328__) || defined (__AVR_ATmega328P__)
    ADMUX = _BV(REFS0) | _BV(MUX3) | _BV(MUX2) | _BV(MUX1);
#elif defined(__AVR_ATmega32U4__) || defined(__AVR_ATmega1280__) || defined(__AVR_ATmega2560__) || defined(__AVR_AT90USB1286__)
    ADMUX = _BV(REFS0) | _BV(MUX4) | _BV(MUX3) | _BV(MUX2) | _BV(MUX1);
    ADCSRB &= ~_BV(MUX5);   // Without this the function always returns -1 on the ATmega2560 http://openenergymonitor.org/emon/node/2253#comment-11432
#elif defined (__AVR_ATtiny24__) || defined(__AVR_ATtiny44__) || defined(__AVR_ATtiny84__)
    ADMUX = _BV(MUX5) | _BV(MUX0);
#elif defined (__AVR_ATtiny25__) || defined(__AVR_ATtiny45__) || defined(__AVR_ATtiny85__)
    ADMUX = _BV(MUX3) | _BV(MUX2);
#endif
#if defined(__AVR__)
    delay(2);                                        // Wait for Vref to settle
    ADCSRA |= _BV(ADSC);                             // Convert
    while (bit_is_set(ADCSRA, ADSC));
    result = ADCL;
    result |= ADCH << 8;
    result = 1126400L / result;  //1100mV*1024 ADC steps http://openenergymonitor.org/emon/node/1186
    return result;
#elif defined(__arm__)
    return (3300);                                  //Arduino Due
#else
    return (3300);                                  //Guess that other un-supported architectures will be running a 3.3V!
#endif
}


//END
//THANK YOU