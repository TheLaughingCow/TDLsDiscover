import subprocess
import time
import os
import sys
import random
import concurrent.futures
from queue import Queue
from threading import Lock, Event

def color(text, code):
    return f"\033[{code}m{text}\033[0m"

BLUE = "0;34"
GREEN = "0;32"
RED = "0;31"
YELLOW = "1;33"
PINK = "1;35"

log_lock = Lock()
stop_event = Event()

def check_required_commands():
    for cmd in ['whois', 'dig']:
        if subprocess.call(['which', cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            print(color(f"⛔ Command '{cmd}' is not installed.", RED))
            sys.exit(1)

def is_domain_available(output):
    output = output.lower().strip()
    available_keywords = [
        "no data found", "no match", "not found", "no object found",
        "domain not exist", "is available for registration", "available for registration",
        "free", "available"
    ]
    lines = output.split("\n")
    for line in lines:
        line = line.strip()
        if any(keyword in line for keyword in available_keywords):
            return True
    return False

def is_domain_active(output):
    if "available" in output or "free" in output:
        return False
    active_keywords = ["domain:", "status: active", "eppstatus: active", "domain status"]
    return all(keyword in output for keyword in ["domain:", "status: active"]) or any(keyword in output for keyword in active_keywords)

def check_tld(domain, log_file):
    if stop_event.is_set():
        return
    
    try:
        result = subprocess.run(['whois', domain], capture_output=True, text=True, check=True)
        output = result.stdout.lower().strip()
    except subprocess.CalledProcessError as e:
        print(f"{color('🔗', BLUE)} {domain} -> {color('⚠️ WHOIS Error', YELLOW)}")
        return

    if is_domain_available(output):
        print(f"{color('🔗', BLUE)} {domain} -> {color('✅ Available', GREEN)}")
        return

    if is_domain_active(output):
        try:
            ip_result = subprocess.run(['dig', '+short', domain], capture_output=True, text=True, check=True).stdout.strip()
            if ip_result:
                with log_lock:
                    with open(log_file, 'a', encoding='utf-8') as log:
                        log.write(f"{domain} -> IP found: {ip_result}\nWHOIS:\n{result.stdout}\n")
                print(f"{color('🔗', RED)} {domain} -> {color('⛔ ', RED)}{color('✨ ', YELLOW)} IP: {color(ip_result, RED)}")
            else:
                with log_lock:
                    with open(log_file, 'a', encoding='utf-8') as log:
                        log.write(f"{domain} -> Active without IP\nWHOIS:\n{result.stdout}\n")
                print(f"{color('🔗', RED)} {domain} -> {color('⛔ ', RED)} {color('⚠️ No associated IP', YELLOW)}")
        except subprocess.CalledProcessError:
            print(f"{color('🔗', BLUE)} {domain} -> {color('⚠️ DIG error', YELLOW)}")

def worker(queue, log_file):
    while not queue.empty() and not stop_event.is_set():
        domain = queue.get()
        check_tld(domain, log_file)
        time.sleep(random.uniform(1, 3))
        queue.task_done()

def check_tlds(base_domain, tlds_file, log_file, max_threads=5):
    if not os.path.exists(tlds_file):
        print(color(f"⛔ File {tlds_file} does not exist.", RED))
        return
    
    print(color(f"\n🔎 Starting TLD verification from {tlds_file}...\n", BLUE))
    with open(log_file, 'a', encoding='utf-8') as log:
        log.write(f"{time.ctime()} - Starting verification for {base_domain}\n")
    
    queue = Queue()
    with open(tlds_file, 'r', encoding='utf-8') as f:
        for tld in f:
            tld = tld.strip()
            if tld:
                queue.put(f"{base_domain}{tld}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [executor.submit(worker, queue, log_file) for _ in range(max_threads)]
        try:
            concurrent.futures.wait(futures)
        except KeyboardInterrupt:
            stop_event.set()
            print(color("\n⏹️ User interruption. Clean exit.", RED))
            executor.shutdown(wait=False)
            sys.exit(0)
    
    queue.join()
    with open(log_file, 'a', encoding='utf-8') as log:
        log.write(f"{time.ctime()} - Verification completed for {base_domain}\n")
    
    print(color(f"\n✅ Verification complete. Results saved in: {log_file}\n", GREEN))

def main():
    try:
        check_required_commands()
        domain = input("👉 Enter the target domain name (e.g., amazon): ").strip()
        if not domain:
            print(color("⛔ No domain entered. Exiting program.", RED))
            return

        log_file = f"{domain}_tlds_results.log"
        check_tlds(domain, "tlds_single_dot.txt", log_file)

        while True:
            response = input("\nWould you also like to check multiple TLDs? (Y/N) ").strip().lower()
            if response == 'y':
                check_tlds(domain, "tlds_multiple_dots.txt", log_file)
                break
            elif response == 'n':
                print(color(f"✅ Script completed. Results saved in: {log_file}", GREEN))
                break
            else:
                print(color("⚠️ Invalid response. Please enter 'Y' or 'N'.", YELLOW))
    except KeyboardInterrupt:
        print(color("\n⏹️ User interruption. Clean exit.", RED))
        sys.exit(0)

if __name__ == "__main__":
    main()