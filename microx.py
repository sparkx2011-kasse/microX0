import cv2
import numpy as np
import time

# استيراد المكتبات الأساسية للهاردوير
try:
    import serial
except ImportError:
    serial = None
    print("Warning: 'serial' library not found. Serial communication disabled.")

try:
    import RPi.GPIO as GPIO # type: ignore
except (ImportError, RuntimeError):
    GPIO = None

try:
    from hx711 import HX711
except ImportError:
    HX711 = None
    print("Warning: 'hx711' library not found.")

    
# --- 1. الإعدادات والثوابت (Global Configurations) ---
PUMP_PIN = 18          # منفذ مضخة الشفط
ALARM_PIN = 24         # منفذ التنبيه (ضوء/صوت)
MAX_TANK_CAPACITY = 500 # السعة القصوى للخزان (جرام)
autonomous_mode = True  # وضع التشغيل الافتراضي

# إعدادات السيريال (الاتصال بالأردوينو)
# تعريف الاتصال بالأردوينو عبر USB
try:
    # ملاحظة: إذا كنتِ تجربين على ويندوز حالياً، استخدمي 'COM3' أو 'COM4'
    ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1) 
    time.sleep(2) # انتظار ثانيتين ليتعرف الأردوينو على الاتصال
    print("Arduino Connected!")
except:
    ser = None
    print("Arduino NOT connected - Running in Simulation Mode")

# أحرف الأوامر المرسلة للأردوينو
MOVE_FORWARD = 'F'
MOVE_LEFT    = 'L'
MOVE_RIGHT   = 'R'
STOP         = 'S'
EMERGENCY_BACK = 'B'
ATTACK_COMMAND = 'A'   # للهجوم على البلاستيك
VIBRATE_REMOTE = 'V'   # لهز إيد البلايستيشن
ASCEND_SURFACE = 'U'   # أمر الصعود للسطح (Up)
RETURN_HOME    = 'H'   # أمر العودة لنقطة البداية

# نطاقات الألوان (HSV)
# ألوان معدلة لتعمل بشكل أفضل في إضاءة الغرفة
# تضييق نطاق المرجان (عشان ما يلقط كل شيء برتقالي)
lower_coral = np.array([5, 150, 100]) 
upper_coral = np.array([15, 255, 255])

# توسيع نطاق البلاستيك الأزرق (عشان يلقطه بسهولة أكبر)
lower_plastic = np.array([100, 50, 50]) 
upper_plastic = np.array([140, 255, 255])

# إعدادات المداخل والمخارج (GPIO)
try:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PUMP_PIN, GPIO.OUT)
    GPIO.setup(ALARM_PIN, GPIO.OUT)
    hx = HX711(5, 6) # توصيل حساس الوزن
    hx.set_reference_unit(1)
    hx.tare()
except:
    hx = None

# --- 2. دوال التحليل والقياس ---

def get_info(mask):
    """تحليل الصورة لاستخراج أكبر جسم وموقعه"""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        M = cv2.moments(largest)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            return area, cX
    return 0, 0

def get_tank_weight():
    """قراءة الوزن الفعلي من الحساس"""
    if hx:
        return max(0, hx.get_weight(5))
    return 0

# --- 3. محرك اتخاذ القرار (الذكاء الاصطناعي) ---

def microx_decision_engine(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    height, width, _ = frame.shape
    
    # رسم خطوط تقسيم الشاشة للمعالجة البصرية
    cv2.line(frame, (width//3, 0), (width//3, height), (255, 0, 0), 2)
    cv2.line(frame, (2*width//3, 0), (2*width//3, height), (255, 0, 0), 2)

    # فحص امتلاء الخزان
    current_weight = get_tank_weight()
    if current_weight >= MAX_TANK_CAPACITY:
        return "GO_HOME_PROTOCOL" # تفعيل بروتوكول العودة

    # فحص المرجان (أولوية قصوى للهروب)
    coral_mask = cv2.inRange(hsv, lower_coral, upper_coral)
    c_area, c_x = get_info(coral_mask)
    if c_area > 400: # إذا وجد مرجان قريب
        if c_x < (width / 3): return MOVE_RIGHT # المرجان يسار -> اذهب يمين
        elif c_x > (2 * width / 3): return MOVE_LEFT # المرجان يمين -> اذهب يسار
        else: return EMERGENCY_BACK # المرجان في الوسط -> ارجع للخلف

    # فحص البلاستيك (الاستهداف)
    plastic_mask = cv2.inRange(hsv, lower_plastic, upper_plastic)
    p_area, p_x = get_info(plastic_mask)
    if 300 < p_area < 5000:# إذا وجد بلاستيك بحجم مناسب
        if (width / 3) < p_x < (2 * width / 3): return "ATTACK_PLASTIC"
        elif p_x < (width / 3): return MOVE_LEFT
        else: return MOVE_RIGHT
# القاعدة : لا توجد عوائق أو أهداف
    return MOVE_FORWARD

# --- 4. تنفيذ الأوامر (Hardware Control) ---

def execute_action(action):
    global autonomous_mode
    # تحويل القرار لحرف واحد يفهمه الأردوينو
    command = 'S' # الافتراضي توقف
    
    if action == "MOVE_FORWARD": command = 'F'
    elif action == "MOVE_LEFT":  command = 'L'
    elif action == "MOVE_RIGHT": command = 'R'
    elif action == "EMERGENCY_BACK": command = 'B'
    elif action == "ATTACK_PLASTIC": command = 'A'
    elif action == "GO_HOME_PROTOCOL": command = 'H'

    # إرسال الحرف عبر الـ USB
    if ser and ser.is_open:
        ser.write(command.encode())
    
    #3.  دالة قراءة كبسة (X):
    # بروتوكول العودة عند الامتلاء
    if action == "GO_HOME_PROTOCOL":
        print("ALERT: Tank Full! Ascending and Returning...")
        try:
            GPIO.output(PUMP_PIN, GPIO.LOW)   # إطفاء الشفط فوراً
            GPIO.output(ALARM_PIN, GPIO.HIGH) # تشغيل التنبيه
        except: pass
        
        if ser:
            ser.write(VIBRATE_REMOTE.encode()) # هز إيد البلايستيشن للتنبيه
            time.sleep(0.5)
            ser.write(ASCEND_SURFACE.encode()) # أمر الصعود للسطح
            time.sleep(2)
            ser.write(RETURN_HOME.encode())    # أمر العودة للمكان المحدد
        return

    # حالة الهجوم على البلاستيك
    if action == "ATTACK_PLASTIC":
        print("STATUS: Capturing Plastic...")
        try: GPIO.output(PUMP_PIN, GPIO.HIGH)
        except: pass
        if ser: ser.write(ATTACK_COMMAND.encode())
        
    # حالات الهروب من المرجان
    elif action in [MOVE_LEFT, MOVE_RIGHT, EMERGENCY_BACK]:
        try: GPIO.output(PUMP_PIN, GPIO.LOW) # حماية المرجان بإطفاء الشفط
        except: pass
        if ser: ser.write(action.encode())
        
    # حالة الحركة للأمام
    elif action == MOVE_FORWARD:
        try: GPIO.output(PUMP_PIN, GPIO.LOW)
        except: pass
        if ser: ser.write(MOVE_FORWARD.encode())

def check_manual_toggle():
    """التبديل بين الذاتي واليدوي باستخدام كبسة X"""
    global autonomous_mode
    # التأكد من وجود اتصال ومن وجود بيانات تنتظر القراءة
    if ser and ser.in_waiting > 0:
        try:
            # قراءة السطر القادم من الأردوينو
            line = ser.readline().decode('utf-8').strip()
            
            if line == "BUTTON_X":
                autonomous_mode = not autonomous_mode
                print(f"--- Mode Switched. AI Status: {autonomous_mode} ---")
            
            return line # نعيد السطر في حال أردنا استخدامه لأوامر أخرى لاحقاً
        except Exception as e:
            # في حال حدث خطأ في القراءة، نطبعه للتشخيص ولا نوقف البرنامج
            print(f"Serial Read Error: {e}")
            return None
    return None

# --- 5. نظام التشغيل الرئيسي ---

def start_microx():
    global autonomous_mode
    cap = cv2.VideoCapture(1)
    
    # تحسين دقة الكاميرا (اختياري)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("MicroX Fully Loaded. System Ready.")
    
    while True:
        ret, frame = cap.read()
        if not ret: break

        check_manual_toggle()

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # إنشاء "ماسك" للفحص (عشان نشوف شو الكاميرا شايفة)
        coral_mask = cv2.inRange(hsv, lower_coral, upper_coral)
        plastic_mask = cv2.inRange(hsv, lower_plastic, upper_plastic)

        
        if autonomous_mode:
            decision = microx_decision_engine(frame)
            execute_action(decision)
            cv2.putText(frame, f"AI Mode: {decision}", (10, 30), 1, 2, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "MANUAL MODE", (10, 30), 1, 2, (0, 0, 255), 2)

        # عرض النافذة الرئيسية
        cv2.imshow("Operational View", frame)
        
        # --- نوافذ الفحص (مهمة جداً للتجربة) ---
        # هي النوافذ بتورجيك باللون الأبيض الأشياء اللي لقطها الكود كبلاستيك أو مرجان
        cv2.imshow("Plastic Detection (Mask)", plastic_mask)
        cv2.imshow("Coral Detection (Mask)", coral_mask)

        # الخروج عند ضغط q
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()
    try: GPIO.cleanup()
    except: pass

if __name__ == "__main__":
    start_microx()