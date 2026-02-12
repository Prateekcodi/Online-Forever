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
# Send status (fixed version - no more errors)
# ────────────────────────────────────────────────
async def send_status_quick(token, status):
    try:
        async with websockets.connect(
            "wss://gateway.discord.gg/?v=9&encoding=json",
            max_size=None,          # This fixes the "message too big" error forever
            ping_interval=None,
            ping_timeout=None
        ) as ws:
            # Wait for HELLO
            start = json.loads(await ws.recv())
            heartbeat = start["d"]["heartbeat_interval"]

            # Get fresh LeetCode count
            solved = get_leetcode_solved()
            print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] LeetCode solved: {solved}")
            custom_text = f"LeetCode Solved: {solved} 🔥"

            # Identify (login)
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

            # Send custom status
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
            await ws.send(json.dumps(cstatus))
            print(f"{Fore.WHITE}[{Fore.LIGHTGREEN_EX}+{Fore.WHITE}] Custom status sent: {custom_text}")

            # One heartbeat then close
            await asyncio.sleep(heartbeat / 1000 * 1.1)
            await ws.send(json.dumps({"op": 1, "d": "None"}))
            await asyncio.sleep(2)

    except Exception as e:
        print(f"{Fore.RED}Error: {e}")
        raise

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