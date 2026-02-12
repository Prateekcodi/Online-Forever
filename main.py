import os
import sys
import json
import asyncio
import platform
import requests
import websockets
import random
import time  # ← FIXED: import time for time.time()
from colorama import init, Fore
from keep_alive import keep_alive

init(autoreset=True)

# Config
DISCORD_STATUS = "online"
LEETCODE_USERNAME = "Prateek_pal"

usertoken = os.getenv("TOKEN", "").strip()
if not usertoken:
    print(f"{Fore.RED}No TOKEN found in env vars. Add it in Render → Environment Variables.")
    sys.exit()

# Quick token check
headers = {"Authorization": usertoken, "Content-Type": "application/json"}
validate = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
if validate.status_code != 200:
    print(f"{Fore.RED}Token invalid (HTTP {validate.status_code}). Get fresh one from browser DevTools.")
    sys.exit()

userinfo = validate.json()
username = userinfo["username"]
userid = userinfo["id"]

def get_leetcode_solved():
    try:
        url = "https://leetcode.com/graphql"
        payload = {
            "query": """
            query getUserProfile($username: String!) {
              matchedUser(username: $username) {
                submitStatsGlobal { acSubmissionNum { difficulty count } }
              }
            }
            """,
            "variables": {"username": LEETCODE_USERNAME}
        }
        resp = requests.post(url, json=payload, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        subs = data.get("data", {}).get("matchedUser", {}).get("submitStatsGlobal", {}).get("acSubmissionNum", [])
        total = next((s["count"] for s in subs if s.get("difficulty") == "All"), 0)
        if total == 0:
            total = sum(s["count"] for s in subs)
        return str(total) if total > 0 else "N/A"
    except Exception as e:
        print(f"{Fore.YELLOW}LeetCode fetch failed: {e}")
        return "Fetch Error"

async def gateway_loop():
    os.system("cls" if platform.system() == "Windows" else "clear")
    print(f"{Fore.GREEN}[+] Started as {username} ({userid})")
    print(f"{Fore.CYAN}[i] LeetCode username: {LEETCODE_USERNAME}")
    print(f"{Fore.CYAN}[i] Keeping Online + updating status every ~30 min")
    print(f"{Fore.CYAN}[i] Uptime pinger must be active!\n")

    last_status_update = 0

    while True:
        try:
            async with websockets.connect(
                "wss://gateway.discord.gg/?v=9&encoding=json",
                max_size=None,
                ping_interval=35,      # Discord expects ~41s, we use 35s
                ping_timeout=20
            ) as ws:
                hello = json.loads(await ws.recv())
                hb_interval = hello["d"]["heartbeat_interval"] / 1000.0
                print(f"{Fore.CYAN}[+] Connected | Heartbeat every ~{hb_interval:.0f}s")

                # Identify
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
                        "large_threshold": 50,  # Smaller = less data
                        "intents": 0  # No events needed, just presence
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

                        if op == 0:  # READY or other dispatch
                            if data.get("t") == "READY":
                                print(f"{Fore.GREEN}[+] READY authenticated!")
                        elif op == 1:  # Heartbeat request from Discord
                            await ws.send(json.dumps({"op": 1, "d": seq}))
                        elif op == 11:  # HB ACK
                            pass

                        seq = data.get("s", seq)

                        # Update custom status every 30 min
                        current_time = time.time()
                        if current_time - last_status_update > 1800:  # 30 minutes
                            solved = get_leetcode_solved()
                            custom_text = f"LeetCode Solved: {solved} 🔥"

                            presence_payload = {
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
                            await ws.send(json.dumps(presence_payload))
                            print(f"{Fore.GREEN}[+] Status updated: {custom_text}")
                            last_status_update = current_time

                    except asyncio.TimeoutError:
                        # Send heartbeat
                        await ws.send(json.dumps({"op": 1, "d": seq}))
                        print(f"{Fore.CYAN}[HB] Sent")

        except websockets.exceptions.ConnectionClosed as e:
            print(f"{Fore.YELLOW}Disconnected (code {e.code}): {e.reason}")
            if e.code == 4004:
                print(f"{Fore.RED}4004 → Token/session killed by Discord. Get fresh token from browser → update env → redeploy.")
            await asyncio.sleep(30 + random.randint(0, 60))  # Backoff + jitter
        except Exception as e:
            print(f"{Fore.RED}Loop error: {e}")
            await asyncio.sleep(60)

keep_alive()
asyncio.run(gateway_loop())