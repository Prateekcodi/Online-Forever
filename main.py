import os
import sys
import json
import asyncio
import platform
import requests
import websockets
import random
import time
from colorama import init, Fore
from keep_alive import keep_alive

init(autoreset=True)

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────
DISCORD_STATUS = "online"

LEETCODE_USERNAME = "Prateek_pal"

# From your Discord Developer Application (exactly from screenshot)
APPLICATION_ID = "1471509621888782582"

# Rich Presence assets (exactly as in your screenshot)
LARGE_IMAGE_KEY  = "time"
LARGE_IMAGE_TEXT = "Numbani"

SMALL_IMAGE_KEY  = "time"
SMALL_IMAGE_TEXT = "Rogue - Level 100"

# Fancy/crazy playing text (you can change these)
PLAYING_NAME = "Hacking the Matrix"
DETAILS_TEMPLATE = "LeetCode Solved: {solved}"
STATE_TEMPLATE   = "Streak: {streak} days 🔥 Mad Coding"

usertoken = os.getenv("TOKEN", "").strip()
if not usertoken:
    print(f"{Fore.RED}No TOKEN in environment variables.")
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}
validate = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
if validate.status_code != 200:
    print(f"{Fore.RED}Token invalid (HTTP {validate.status_code}). Get fresh token from browser.")
    sys.exit()

userinfo = validate.json()
username = userinfo["username"]
userid = userinfo["id"]

def get_leetcode_stats():
    try:
        url = "https://leetcode.com/graphql"
        payload = {
            "query": """
            query getUserStats($username: String!) {
              matchedUser(username: $username) {
                submitStatsGlobal { acSubmissionNum { difficulty count } }
                userCalendar { streak totalActiveDays }
              }
            }
            """,
            "variables": {"username": LEETCODE_USERNAME}
        }
        resp = requests.post(url, json=payload, timeout=12)
        resp.raise_for_status()
        data = resp.json()["data"]["matchedUser"]

        subs = data["submitStatsGlobal"]["acSubmissionNum"]
        solved = next((s["count"] for s in subs if s["difficulty"] == "All"), sum(s["count"] for s in subs))

        streak = data["userCalendar"]["streak"] if data.get("userCalendar") else 0

        return solved, streak
    except Exception as e:
        print(f"{Fore.YELLOW}LeetCode fetch failed: {e}")
        return 0, 0

async def gateway_loop():
    os.system("cls" if platform.system() == "Windows" else "clear")
    print(f"{Fore.GREEN}[+] Started as {username} ({userid})")
    print(f"{Fore.CYAN}[i] LeetCode username: {LEETCODE_USERNAME}")
    print(f"{Fore.CYAN}[i] Application ID: {APPLICATION_ID}")
    print(f"{Fore.CYAN}[i] Large image: time | Text: Numbani")
    print(f"{Fore.CYAN}[i] Small image: time | Text: Rogue - Level 100")
    print(f"{Fore.CYAN}[i] Playing: {PLAYING_NAME}")
    print(f"{Fore.CYAN}[i] Updates every ~30 min | Online 24/7\n")

    last_update = 0

    while True:
        try:
            async with websockets.connect(
                "wss://gateway.discord.gg/?v=9&encoding=json",
                max_size=None,
                ping_interval=35,
                ping_timeout=20
            ) as ws:
                hello = json.loads(await ws.recv())
                hb_interval = hello["d"]["heartbeat_interval"] / 1000.0
                print(f"{Fore.CYAN}[+] Connected | Heartbeat ~{hb_interval:.0f}s")

                identify = {
                    "op": 2,
                    "d": {
                        "token": usertoken,
                        "properties": {
                            "$os": platform.system(),
                            "$browser": "Discord Client",
                            "$device": "desktop"
                        },
                        "compress": False,
                        "large_threshold": 50,
                        "intents": 0
                    }
                }
                await ws.send(json.dumps(identify))
                print(f"{Fore.CYAN}[+] Identify sent")

                seq = None
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=hb_interval + 10)
                        data = json.loads(msg)
                        op = data["op"]

                        if op == 0 and data.get("t") == "READY":
                            print(f"{Fore.GREEN}[+] READY authenticated!")
                        elif op == 1:
                            await ws.send(json.dumps({"op": 1, "d": seq}))
                        elif op == 11:
                            pass

                        seq = data.get("s", seq)

                        # Update status every 30 minutes
                        if time.time() - last_update > 1800:
                            solved, streak = get_leetcode_stats()
                            details_text = DETAILS_TEMPLATE.format(solved=solved)
                            state_text   = STATE_TEMPLATE.format(streak=streak)

                            activity = {
                                "application_id": APPLICATION_ID,
                                "type": 0,  # Playing
                                "name": PLAYING_NAME,
                                "details": details_text,
                                "state": state_text,
                                "timestamps": {"start": int(time.time() * 1000) - random.randint(300, 3600)},
                                "assets": {
                                    "large_image": LARGE_IMAGE_KEY,
                                    "large_text": LARGE_IMAGE_TEXT,
                                    "small_image": SMALL_IMAGE_KEY,
                                    "small_text": SMALL_IMAGE_TEXT
                                } if LARGE_IMAGE_KEY else {}
                            }

                            payload = {
                                "op": 3,
                                "d": {
                                    "since": 0,
                                    "activities": [activity],
                                    "status": DISCORD_STATUS,
                                    "afk": False
                                }
                            }
                            await ws.send(json.dumps(payload))
                            print(f"{Fore.GREEN}[+] Status sent: {PLAYING_NAME} | {details_text} | {state_text}")
                            last_update = time.time()

                    except asyncio.TimeoutError:
                        await ws.send(json.dumps({"op": 1, "d": seq}))
                        print(f"{Fore.CYAN}[HB] Sent")

        except websockets.exceptions.ConnectionClosed as e:
            print(f"{Fore.YELLOW}Disconnected ({e.code}): {e.reason or 'Unknown'}")
            if e.code == 4004:
                print(f"{Fore.RED}4004 → Token invalidated. Get fresh token from browser DevTools → update env var → redeploy")
            await asyncio.sleep(30 + random.randint(0, 60))
        except Exception as e:
            print(f"{Fore.RED}Error: {e}")
            await asyncio.sleep(60)

keep_alive()
asyncio.run(gateway_loop())