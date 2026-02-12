import os
import sys
import json
import asyncio
import platform
import requests
import websockets
from colorama import init, Fore
from keep_alive import keep_alive

init(autoreset=True)

# ────────────────────────────────────────────────
# CONFIG - ONLY CHANGE HERE IF YOU WANT
# ────────────────────────────────────────────────
DISCORD_STATUS = "online"           # online / dnd / idle
LEETCODE_USERNAME = "Prateek_pal"   # Your LeetCode username (already correct)

usertoken = os.getenv("TOKEN")
if not usertoken:
    print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] Please add a token inside Secrets.")
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}

# Validate token
validate = requests.get("https://canary.discordapp.com/api/v9/users/@me", headers=headers)
if validate.status_code != 200:
    print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] Your token might be invalid. Please check it again.")
    sys.exit()

userinfo = validate.json()
username = userinfo["username"]
userid = userinfo["id"]

# ────────────────────────────────────────────────
# LeetCode fetch function
# ────────────────────────────────────────────────
def get_leetcode_solved():
    url = "https://leetcode.com/graphql"
    query = """
    query getUserProfile($username: String!) {
      matchedUser(username: $username) {
        submitStatsGlobal {
          acSubmissionNum {
            difficulty
            count
          }
        }
      }
    }
    """
    payload = {
        "query": query,
        "variables": {"username": LEETCODE_USERNAME},
        "operationName": "getUserProfile"
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        submissions = data.get("data", {}).get("matchedUser", {}).get("submitStatsGlobal", {}).get("acSubmissionNum", [])
        if not submissions:
            return "N/A"
        total = next((item["count"] for item in submissions if item["difficulty"] == "All"), 0)
        if total == 0:
            total = sum(item["count"] for item in submissions if item["difficulty"] != "All")
        return str(total)
    except:
        return "Error"

# ────────────────────────────────────────────────
# Send status (fixed: wait for READY before sending op 3)
# ────────────────────────────────────────────────
async def send_status_quick(token, status):
    try:
        async with websockets.connect(
            "wss://gateway.discord.gg/?v=9&encoding=json",
            max_size=None,          # Fixes "message too big"
            ping_interval=None,
            ping_timeout=None
        ) as ws:
            # Receive HELLO (op 10)
            hello = json.loads(await ws.recv())
            heartbeat_interval = hello["d"]["heartbeat_interval"]
            print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] Received HELLO")

            # Send IDENTIFY (op 2)
            auth = {
                "op": 2,
                "d": {
                    "token": token,
                    "properties": {
                        "$os": "Windows 10",
                        "$browser": "Google Chrome",
                        "$device": "Windows",
                    },
                    "presence": {"status": status, "afk": False},
                    "compress": False,
                },
            }
            await ws.send(json.dumps(auth))
            print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] Identify sent")

            # Get fresh LeetCode count
            solved = get_leetcode_solved()
            print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] LeetCode solved: {solved}")
            custom_text = f"LeetCode Solved: {solved} 🔥"

            # Prepare custom status (op 3)
            cstatus = {
                "op": 3,
                "d": {
                    "since": 0,
                    "activities": [
                        {
                            "type": 4,
                            "state": custom_text,
                            "name": "Custom Status",
                            "id": "custom"
                        }
                    ],
                    "status": status,
                    "afk": False,
                },
            }

            # Now loop to receive events until READY (op 0)
            heartbeat_task = None
            ready_received = False
            while not ready_received:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=heartbeat_interval / 1000)
                    data = json.loads(message)
                    op = data["op"]

                    if op == 10:  # HELLO (should already be handled)
                        pass
                    elif op == 11:  # HEARTBEAT_ACK
                        print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] Heartbeat ACK received")
                    elif op == 0:  # DISPATCH (e.g., READY)
                        if data["t"] == "READY":
                            ready_received = True
                            print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] Received READY")
                            # Now send custom status
                            await ws.send(json.dumps(cstatus))
                            print(f"{Fore.WHITE}[{Fore.LIGHTGREEN_EX}+{Fore.WHITE}] Custom status sent: {custom_text}")
                    elif op == 1:  # HEARTBEAT request
                        await ws.send(json.dumps({"op": 1, "d": None}))
                        print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] Heartbeat sent")

                    # Ignore other events for now

                except asyncio.TimeoutError:
                    # Send heartbeat if timeout (no message)
                    await ws.send(json.dumps({"op": 1, "d": None}))
                    print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] Heartbeat sent (timeout)")

            # After sending status, wait a bit and close
            await asyncio.sleep(5)

    except Exception as e:
        print(f"{Fore.RED}Error: {e}")

# ────────────────────────────────────────────────
# Main loop
# ────────────────────────────────────────────────
async def run_onliner():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")
    
    print(f"{Fore.WHITE}[{Fore.LIGHTGREEN_EX}+{Fore.WHITE}] Logged in as {Fore.LIGHTBLUE_EX}{username} ({userid})!")
    print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] LeetCode: {LEETCODE_USERNAME}")
    print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] Status updates every 50 seconds")
    print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] Your service is live at your Render URL\n")

    while True:
        try:
            await send_status_quick(usertoken, DISCORD_STATUS)
        except:
            print(f"{Fore.YELLOW}Reconnecting in 10 seconds...")
        
        await asyncio.sleep(50)

keep_alive()
asyncio.run(run_onliner())