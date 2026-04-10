#include <PS2X_lib.h>

// دبابيس ريسيفر البلايستيشن
#define PS2_DAT        12    
#define PS2_CMD        11  
#define PS2_SEL        10  
#define PS2_CLK        13  

// دبابيس المواتير
#define M_R1 2
#define M_R2 3
#define M_L1 4
#define M_L2 5

PS2X ps2x;
bool isManual = false; // متغير لتحديد هل نحن في وضع يدوي أم آلي

void setup() {
  Serial.begin(9600);
  pinMode(M_R1, OUTPUT); pinMode(M_R2, OUTPUT);
  pinMode(M_L1, OUTPUT); pinMode(M_L2, OUTPUT);
  
  // إعداد الإيد
  ps2x.config_gamepad(PS2_CLK, PS2_CMD, PS2_SEL, PS2_DAT, true, true);
}

void loop() {
  ps2x.read_gamepad(); // قراءة مستمرة للإيد

  // 1. التبديل بين اليدوي والآلي عند ضغط زر X
  if(ps2x.ButtonPressed(PSB_BLUE)) { 
    isManual = !isManual; // عكس الحالة
    Serial.println("BUTTON_X"); // إبلاغ الراسبيري بتغيير الحالة لتحديث الشاشة
    stopMotors();
  }

  // 2. إذا كنا في الوضع اليدوي: التحكم مباشرة من الجويستيك
  if (isManual) {
    handleManualControl();
  } 
  // 3. إذا كنا في الوضع الآلي: استقبال الأوامر من الراسبيري
  else {
    if (Serial.available() > 0) {
      char cmd = Serial.read();
      executeAICommand(cmd);
    }
  }
  delay(50);
}

// دالة التحكم اليدوي (باستخدام الجويستيك)
void handleManualControl() {
  int y = ps2x.Analog(PSS_LY); // الحركة للأمام والخلف
  int x = ps2x.Analog(PSS_RX); // الدوران يمين ويسار

  if (y < 100) moveForward();
  else if (y > 150) moveBack();
  else if (x < 100) moveLeft();
  else if (x > 150) moveRight();
  else stopMotors();
}

// دالة تنفيذ أوامر الذكاء الاصطناعي (القادمة من الراسبيري)
void executeAICommand(char command) {
  switch (command) {
    case 'F': moveForward(); break;
    case 'B': moveBack();    break;
    case 'L': moveLeft();    break;
    case 'R': moveRight();   break;
    case 'S': stopMotors();  break;
    case 'V': // تشغيل هزاز الإيد عند امتلاء الخزان
      ps2x.read_gamepad(true, 200); delay(500); ps2x.read_gamepad(false, 0); 
      break;
  }
}

// --- دوال الحركة الأساسية ---
void moveForward() { digitalWrite(M_R1, HIGH); digitalWrite(M_R2, LOW); digitalWrite(M_L1, HIGH); digitalWrite(M_L2, LOW); }
void moveBack()    { digitalWrite(M_R1, LOW);  digitalWrite(M_R2, HIGH); digitalWrite(M_L1, LOW);  digitalWrite(M_L2, HIGH); }
void moveLeft()    { digitalWrite(M_R1, HIGH); digitalWrite(M_R2, LOW);  digitalWrite(M_L1, LOW);  digitalWrite(M_L2, LOW);  }
void moveRight()   { digitalWrite(M_R1, LOW);  digitalWrite(M_R2, LOW);  digitalWrite(M_L1, HIGH); digitalWrite(M_L2, LOW);  }
void stopMotors()  { digitalWrite(M_R1, LOW);  digitalWrite(M_R2, LOW);  digitalWrite(M_L1, LOW);  digitalWrite(M_L2, LOW);  }