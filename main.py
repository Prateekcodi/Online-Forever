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
DISCORD_STATUS = "online"
LEETCODE_USERNAME = "Prateek_pal"

usertoken = os.getenv("TOKEN").strip()  # .strip() removes accidental whitespace/newlines
if not usertoken:
    print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] No TOKEN in env vars. Add it in Render Secrets.")
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}

validate = requests.get("https://discord.com/api/v9/users/@me", headers=headers)  # Use production endpoint
if validate.status_code != 200:
    print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] Token invalid right now (HTTP {validate.status_code}). Regenerate it from browser.")
    print(validate.text)
    sys.exit()

userinfo = validate.json()
username = userinfo["username"]
userid = userinfo["id"]

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
    payload = {"query": query, "variables": {"username": LEETCODE_USERNAME}}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        subs = data.get("data", {}).get("matchedUser", {}).get("submitStatsGlobal", {}).get("acSubmissionNum", [])
        total = next((s["count"] for s in subs if s["difficulty"] == "All"), 0)
        if total == 0:
            total = sum(s["count"] for s in subs)
        return str(total) if total else "N/A"
    except Exception as e:
        print(f"LeetCode error: {e}")
        return "Error"

async def send_status_quick(token, status):
    try:
        async with websockets.connect(
            "wss://gateway.discord.gg/?v=9&encoding=json",
            max_size=None,
            ping_interval=None,
            ping_timeout=None
        ) as ws:
            hello = json.loads(await ws.recv())
            hb_interval = hello["d"]["heartbeat_interval"]
            print(f"{Fore.CYAN}[DEBUG] HELLO received")

            auth = {
                "op": 2,
                "d": {
                    "token": token,
                    "properties": {"$os": platform.system(), "$browser": "Chrome", "$device": "PC"},
                    "presence": {"status": status, "afk": False},
                    "compress": False,
                }
            }
            await ws.send(json.dumps(auth))
            print(f"{Fore.CYAN}[DEBUG] Identify sent")

            solved = get_leetcode_solved()
            print(f"{Fore.CYAN}[DEBUG] LeetCode: {solved}")
            custom_text = f"LeetCode Solved: {solved} 🔥"

            cstatus = {
                "op": 3,
                "d": {
                    "since": 0,
                    "activities": [{"type": 4, "state": custom_text, "name": "Custom Status", "id": "custom"}],
                    "status": status,
                    "afk": False
                }
            }

            ready_received = False
            while not ready_received:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=hb_interval / 1000)
                    data = json.loads(msg)
                    op = data.get("op")

                    if op == 0 and data.get("t") == "READY":
                        ready_received = True
                        print(f"{Fore.CYAN}[DEBUG] READY received - authenticated!")
                        await ws.send(json.dumps(cstatus))
                        print(f"{Fore.GREEN}[+] Status sent: {custom_text}")
                    elif op == 1:
                        await ws.send(json.dumps({"op": 1, "d": None}))
                    # Ignore other ops

                except asyncio.TimeoutError:
                    await ws.send(json.dumps({"op": 1, "d": None}))

            await asyncio.sleep(5)  # Give time for delivery

    except websockets.exceptions.ConnectionClosed as e:
        if e.code == 4004:
            print(f"{Fore.RED}!!! 4004 Authentication failed - TOKEN INVALIDATED !!!")
            print(f"Reason: {e.reason}")
            print("Fix: Log in to Discord browser → get fresh token from DevTools → update Render env var → redeploy")
        else:
            print(f"{Fore.RED}Connection closed: {e.code} - {e.reason}")
    except Exception as e:
        print(f"{Fore.RED}Error: {e}")

async def run_onliner():
    os.system("cls" if platform.system() == "Windows" else "clear")
    print(f"{Fore.GREEN}[+] Logged in as {username} ({userid})")
    print(f"{Fore.CYAN}[i] LeetCode: {LEETCODE_USERNAME}")
    print(f"{Fore.CYAN}[i] Updating every ~5 minutes (slowed to avoid bans)")
    print(f"{Fore.CYAN}[i] Keep uptime pinger running!\n")

    while True:
        await send_status_quick(usertoken, DISCORD_STATUS)
        await asyncio.sleep(300)  # 5 minutes - much safer

keep_alive()
asyncio.run(run_onliner())