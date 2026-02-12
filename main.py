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

# Config
DISCORD_STATUS = "online"
LEETCODE_USERNAME = "Prateek_pal"

usertoken = os.getenv("TOKEN", "").strip()
if not usertoken:
    print(f"{Fore.RED}No TOKEN in env. Add it.")
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}
validate = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
if validate.status_code != 200:
    print(f"{Fore.RED}Token invalid (code {validate.status_code}). Get fresh one.")
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
                submitStatsGlobal {
                  acSubmissionNum {
                    difficulty
                    count
                  }
                }
                userCalendar {
                  streak
                  totalActiveDays
                }
              }
            }
            """,
            "variables": {"username": LEETCODE_USERNAME}
        }
        resp = requests.post(url, json=payload, timeout=12)
        resp.raise_for_status()
        data = resp.json()["data"]["matchedUser"]

        # Total solved
        subs = data["submitStatsGlobal"]["acSubmissionNum"]
        total_solved = next((s["count"] for s in subs if s["difficulty"] == "All"), 0)
        if total_solved == 0:
            total_solved = sum(s["count"] for s in subs)

        # Streak
        streak = data["userCalendar"]["streak"] if data["userCalendar"] else 0

        return total_solved, streak
    except Exception as e:
        print(f"{Fore.YELLOW}Stats fetch failed: {e}")
        return "Error", 0

async def gateway_loop():
    os.system("cls" if platform.system() == "Windows" else "clear")
    print(f"{Fore.GREEN}[+] Started as {username} ({userid})")
    print(f"{Fore.CYAN}[i] LeetCode: {LEETCODE_USERNAME}")
    print(f"{Fore.CYAN}[i] Keeping Online + updating Solved + Streak every ~30 min")
    print(f"{Fore.CYAN}[i] Check from another account!\n")

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
                print(f"{Fore.CYAN}[+] Connected | HB ~{hb_interval:.0f}s")

                identify_payload = {
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
                await ws.send(json.dumps(identify_payload))
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

                        # Update every 30 min
                        if time.time() - last_update > 1800:
                            total, streak = get_leetcode_stats()
                            custom_text = f"Solved: {total} | Streak: {streak} 🔥"

                            presence = {
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
                                    "status": DISCORD_STATUS,
                                    "afk": False
                                }
                            }
                            await ws.send(json.dumps(presence))
                            print(f"{Fore.GREEN}[+] Status updated → {custom_text}")
                            last_update = time.time()

                    except asyncio.TimeoutError:
                        await ws.send(json.dumps({"op": 1, "d": seq}))
                        print(f"{Fore.CYAN}[HB] Sent")

        except websockets.exceptions.ConnectionClosed as e:
            print(f"{Fore.YELLOW}Disconnected ({e.code}): {e.reason}")
            if e.code == 4004:
                print(f"{Fore.RED}4004 DETECTED - Get fresh token from browser DevTools → update Render env → redeploy")
            await asyncio.sleep(30 + random.randint(0, 60))
        except Exception as e:
            print(f"{Fore.RED}Error: {e}")
            await asyncio.sleep(60)

keep_alive()
asyncio.run(gateway_loop())