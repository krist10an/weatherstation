/*
 * Reading Wireless temperature and humidity sensors. Works with WT450, WT450H sensors
 * and using QAM-RX4 as a reciever.
 * WS2015H display not used other than for its original purpose.
 * based on v0.1 code by Jaakko Ala-Paavola 2011-02-27
 * which used the WS2015H as the receiver
 *
 * kt Oct 2011
 *
 * - Add simple recursive filtering
 * krist10an 2016
 */


#include <SPI.h>
#include <MySensor.h>

#include <Time.h>

#define DEBUG 1 //prints additional information to serial port
#define HOUSECODE 3


#define CHILD_ID_HUM 0
#define CHILD_ID_TEMP 1

 MySensor gw;
 MyMessage msgHum1(10, V_HUM);
 MyMessage msgTemp1(11, V_TEMP);
 MyMessage msgHum2(20, V_HUM);
 MyMessage msgTemp2(21, V_TEMP);
 MyMessage msgHum3(30, V_HUM);
 MyMessage msgTemp3(31, V_TEMP);
 MyMessage msgHum4(40, V_HUM);
 MyMessage msgTemp4(41, V_TEMP);


#define TIMEOUT 65000

#define BIT0_LENGTH 2000
#define BIT1_LENGTH 1000
#define VARIATION 500
#define DATA_LENGTH 5
#define SENSOR_COUNT 5
#define NETWORK_COUNT 8
#define MSGLENGTH 36
#define DELAY_BETWEEN_POSTS 5000


 struct sensor {
  unsigned char humidity;
  float         temp;
  boolean updated;
};


struct sensor measurement[NETWORK_COUNT][SENSOR_COUNT+1];

unsigned long time;

unsigned char bitcount = 0;
unsigned char bytecount = 0;
unsigned char second_half = 0;
unsigned char data[DATA_LENGTH];


unsigned long lastPostTimestamp;
unsigned long lastReceivedTimestamp = 0;
unsigned long currentTime;
boolean metric = true;

unsigned long myTimestamp;


/*
 * Linear recursive expontential filter
 * Weight = 0-1 (0-100%)
 * Height weight responds quickly to changes
 * Low smooths out changes
 */
void expFilterF(float &current, float newValue, float weight) {
  current = weight * newValue + (1.0f - weight) * current;
}

void expFilterC(unsigned char &current, unsigned char newValue, unsigned char weight) {
  current = (weight * newValue + (100 - weight) * current) / 100;
}


//int chWithNewData=0;

// This is the interupt driven receive data code
void receive()
{
    //unsigned char i;
    unsigned char bit;
    unsigned long current = micros();
    unsigned long diff = current - time;
    time = current;

    if ((diff < BIT0_LENGTH + VARIATION) && (diff > BIT0_LENGTH - VARIATION))
    {
        bit = 0;
        second_half = 0;
    }
    else if (diff < BIT1_LENGTH + VARIATION && diff > BIT1_LENGTH - VARIATION)
    {
        if (second_half)
        {
            bit = 1;
            second_half = 0;
        }
        else
        {
            second_half = 1;
            return;
        }
    }
    else
    {
        goto reset;
        //reset;
        //return;
    }

    data[bitcount / 8] = data[bitcount / 8] << 1;
    data[bitcount / 8] |= bit;
    bitcount++;

    if (bitcount == 4)
    {
        if (data[0] != 0x0c){
            goto reset;
            //reset();
            //return;
        }
        bitcount = 8;
#ifdef DEBUG
        Serial.print('#');  // data recieved but not sensor data
#endif
    }

    if (bitcount >= MSGLENGTH)
    {
        unsigned char net, id;
        int t_int;
        unsigned char rh, t_dec;

#ifdef DEBUG       // show me the raw data in hex
        for (char i = 0; i < DATA_LENGTH; i++) {
            Serial.print(data[i], HEX);
            Serial.print(' ');
        }
#endif

        Serial.print("NET:");                // Housecode is 1 to 15
        net = 0x0F & (data[1] >> 4);           // the -1 in original code removed
        // 0x07 --> 0x0F to permit NET up to 15 tobe decodeed instead of 7
        if (net <= 9) {                        // just keeping things lined up
            Serial.print(" ");
        }
        Serial.print(net, DEC);
        Serial.print(" ID:");                // Channel is 1 to 4, this and above changed so serial.print agrees with lcd displays
        id = 0x03 & (data[1] >> 2) + 1;
        Serial.print(id, DEC);
        Serial.print(" RH:");                // Only WT450H has a Humidity sensor, WT450 is just Temperature
        rh = data[2];
        if (rh == 0) {                         // just keeping things lined up
            Serial.print(" ");
        }
        Serial.print(rh, DEC);
        Serial.print(" T:");
        t_int = data[3] - 50;
        Serial.print(t_int, DEC);
        t_dec = data[4] >> 1;
        Serial.print('.');
        Serial.print(t_dec, DEC);
        Serial.print(": ");
        Serial.print(time);
        Serial.println("");



        // CSV data out to serial host an alternative to the above

        //       Serial.print("ESIC,");               // The name on the front
        //       net = 0x0F & (data[1]>>4);           // the -1 in original code removed
        //                                            // 0x07 --> 0x0F to permit NET up to 15 tobe decodeed instead of 7
        //       Serial.print(net,DEC);               // Housecode is 1 to 15
        //       Serial.print(",");
        //       id = 0x03 & (data[1]>>2)+1;
        //       Serial.print(id, DEC);               // Channel is 1 to 4, this and above changed so serial.print agrees with lcd displays
        //       Serial.print(",");
        //       rh = data[2];
        //       Serial.print(rh, DEC);               // Only WT450H has a Humidity sensor, WT450 is just Temperature
        //       Serial.print(",");
        //       t_int = data[3]-50;
        //       Serial.print(t_int, DEC);
        //       t_dec = data[4]>>1;
        //       Serial.print('.');
        //       Serial.print(t_dec,DEC);
        //       Serial.println("");

        if (net < NETWORK_COUNT)
        {
            Serial.print("Update measurement ");
            Serial.print(net);
            Serial.print(" ");
            Serial.print(id);
            Serial.println("");

            float temp = t_dec/10.0;
            temp = temp + t_int;

            // Weight of 20 should be good to filter out spurious measurements
            expFilterF(measurement[net][id].temp, temp, 0.2);
            expFilterC(measurement[net][id].humidity, rh, 20);
            measurement[net][id].updated = true;
            lastReceivedTimestamp = millis();
        }
        goto reset;
        //reset();
        //return;
    }
    return;

reset: // set all the receiver variables back to zero
reset();
}
void reset(){
    for (char i=0; i<DATA_LENGTH; i++)
        data[i] = 0;

    bytecount = 0;
    bitcount = 0;
    second_half = 0;
//   return;
}

void setup()
{
  int k,l;
  Serial.begin(115200);

  gw.begin();
  // Send the Sketch Version Information to the Gateway
  gw.sendSketchInfo("Humidity", "2.0");
  // Register all sensors to gw (they will be created as child devices)
  gw.present(10, S_HUM);
  gw.present(11, S_TEMP);
  gw.present(20, S_HUM);
  gw.present(21, S_TEMP);
  gw.present(30, S_HUM);
  gw.present(31, S_TEMP);
  gw.present(40, S_HUM);
  gw.present(41, S_TEMP);

  metric = gw.getConfig().isMetric;

// Serial.println("Wireless Temperature & Humidity Sensors to Serial");
//  Serial.println("Dir --> Wireless_Temp_Serial8");


  for (l=0; l<NETWORK_COUNT; l++)    // the 'network' here is the wireless sensor network
  {
    for (k=0; k<SENSOR_COUNT; k++)
    {
      measurement[l][k].temp = 0;
      measurement[l][k].humidity = 0;
      measurement[l][k].updated = false;
  }
}

Serial.println("Initialise interrupt");
  attachInterrupt(1,receive,CHANGE); // interrupt 0 is pin D2 1 is pin D3
                                     // needs to be 1 for an ENC28J60 ethernet shield

  time = micros();
  lastPostTimestamp = currentTime;
  Serial.println("Setup complete - Waiting for data");

    myTimestamp= millis();
}


boolean newDataReceived(const unsigned int n, const unsigned int c)
{
  if (measurement[n][c].updated==true)
      return true;
  else
      return false;
}


void loop()
{
  currentTime = millis();
  unsigned long time_elapsed = (currentTime - lastPostTimestamp);

  if (currentTime - lastReceivedTimestamp > TIMEOUT)
  {
      lastReceivedTimestamp = currentTime;
      Serial.println("Reset timeout");
      reset();
  }


  if(time_elapsed > DELAY_BETWEEN_POSTS){
   int n = HOUSECODE;

   for (int c=0; c<SENSOR_COUNT; c++)
   {
     if (true == newDataReceived(n,c))
     {
       float temp= measurement[n][c].temp;
       float rh = measurement[n][c].humidity;
       measurement[n][c].updated = false;
       Serial.print("Send n=");
       Serial.print(n);
       Serial.print(" s=");
       Serial.print(c);
       Serial.print(" t=");
       Serial.print(temp);
       Serial.print(" r=");
       Serial.print(rh);
       Serial.print(" timeelapsed: ");
       Serial.print( (currentTime - myTimestamp) );
       Serial.println("");

       myTimestamp = currentTime;

         switch (c)
           {
             case 1:
               gw.send(msgTemp1.set(temp, 1));
               gw.send(msgHum1.set(rh, 1));
               break;
             case 2:
               gw.send(msgTemp2.set(temp, 1));
               gw.send(msgHum2.set(rh, 1));
               break;
             case 3:
               gw.send(msgTemp3.set(temp, 1));
               gw.send(msgHum3.set(rh, 1));
               break;
             case 4:
               gw.send(msgTemp4.set(temp, 1));
               gw.send(msgHum4.set(rh, 1));
               break;
           } //switch

         } // in new data
        } // for sensor count
        lastPostTimestamp = currentTime;
    }
}
