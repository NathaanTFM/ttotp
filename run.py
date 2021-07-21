import subprocess, time, select, threading, sys, msvcrt, os

lock = threading.Lock()
focus = None
output = {}

def reader(proc):
    if not proc:
        return
        
    while True:
        line = proc.stdout.readline()
        if not line:
            break
            
        line = line.decode("utf8").rstrip()
        
        with lock:
            output[proc].pop(0)
            output[proc].append(line)
            if focus == proc:
                print(line)

otp, ud, ai, tt = None, None, None, None

try:
    otp = subprocess.Popen(["py", "-u", "py_otp.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
    
    os.chdir("../ttsrc")
    ud = subprocess.Popen(["built/python/ppython", "-u", "ttrun.py", "-ud"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
    ai = subprocess.Popen(["built/python/ppython", "-u", "ttrun.py", "-ai"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
    tt = subprocess.Popen(["built/python/ppython", "-u", "ttrun.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
    
    for proc in (otp, ud, ai, tt):
        output[proc] = ["-"] * 500
        thread = threading.Thread(target=reader, args=(proc,))
        thread.start()
        
    char = b"1"
    while True:
        if char in b"1234":
            with lock:
                focus = [otp, ud, ai, tt][int(char)-1]
                name = ["OTP Server", "UberDog", "AI", "Toontown"][int(char)-1]
                subprocess.call("title " + str(name), shell=True)
                os.system("cls")
                print("\n".join(output[focus]))
                
        char = msvcrt.getch()
        if char == b"\x03":
            print("detected ctrl^c")
            break
            
        
finally:
    if otp: otp.terminate()
    if ud: ud.terminate()
    if ai: ai.terminate()
    if tt: tt.terminate()
    