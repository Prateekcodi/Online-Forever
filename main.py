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
# CONFIG
# ────────────────────────────────────────────────
status = "online"  # online/dnd/idle
custom_status = "youtube.com/@SeatedSaucer"  # Custom Status
DISCORD_STATUS = "online"           # online / dnd / idle
LEETCODE_USERNAME = "Prateek_pal"  # ← Change this!!
UPDATE_INTERVAL_MINUTES = 30       # How often to refresh LeetCode count

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
discriminator = userinfo.get("discriminator", "")
userid = userinfo["id"]

# ────────────────────────────────────────────────
# LeetCode fetch function
# ────────────────────────────────────────────────
def get_leetcode_solved():
    if not LEETCODE_USERNAME or LEETCODE_USERNAME == "YOUR_LEETCODE_USERNAME_HERE":
        return "Set username"

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

        # Total solved = sum of all difficulties (usually first is All)
        total = next((item["count"] for item in submissions if item["difficulty"] == "All"), 0)
        if total == 0:
            # Fallback: sum easy + medium + hard
            total = sum(item["count"] for item in submissions if item["difficulty"] != "All")

        return str(total)
    except Exception as e:
        print(f"LeetCode fetch error: {e}")
        return "Error"

# ────────────────────────────────────────────────
# Quick WebSocket connection - send status and disconnect
# ────────────────────────────────────────────────
async def send_status_quick(token, status):
    try:
        async with websockets.connect("wss://gateway.discord.gg/?v=9&encoding=json", max_size=1048576) as ws:
            # Wait for HELLO event
            start = json.loads(await ws.recv())
            heartbeat = start["d"]["heartbeat_interval"]

            # Get LeetCode count before identifying
            solved = get_leetcode_solved()
            print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] LeetCode solved: {solved}")
            custom_text = f"LeetCode Solved: {solved} 🔥"

            # Identify with minimal data
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

            # Immediately send status update before READY
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

            # Send one heartbeat and close quickly
            await asyncio.sleep(heartbeat / 1000)
            await ws.send(json.dumps({"op": 1, "d": "None"}))

    except Exception as e:
        print(f"{Fore.RED}Error sending status: {e}")
        raise

# ────────────────────────────────────────────────
# Main loop (send status and reconnect)
# ────────────────────────────────────────────────
async def run_onliner():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")
    
    print(f"{Fore.WHITE}[{Fore.LIGHTGREEN_EX}+{Fore.WHITE}] Logged in as {Fore.LIGHTBLUE_EX}{username} ({userid})!")
    print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] LeetCode username: {LEETCODE_USERNAME}")
    print(f"{Fore.WHITE}[{Fore.CYAN}i{Fore.WHITE}] Sending status every 50 seconds...")

    while True:
        try:
            await send_status_quick(usertoken, DISCORD_STATUS)
        except Exception as e:
            print(f"{Fore.YELLOW}Connection error: {e}. Reconnecting in 10s...")
        
        await asyncio.sleep(50)

keep_alive()
asyncio.run(run_onliner())
