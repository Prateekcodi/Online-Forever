import os
import sys
import json
import asyncio
import platform
import requests
import websockets
import random
from colorama import init, Fore
from keep_alive import keep_alive

init(autoreset=True)

DISCORD_STATUS = "online"
LEETCODE_USERNAME = "Prateek_pal"

usertoken = os.getenv("TOKEN", "").strip()
if not usertoken:
    print(f"{Fore.RED}No TOKEN in env. Add it in Render.")
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}
validate = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
if validate.status_code != 200:
    print(f"{Fore.RED}Token invalid now (code {validate.status_code}). Regenerate from browser.")
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
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        subs = data["data"]["matchedUser"]["submitStatsGlobal"]["acSubmissionNum"]
        total = next((s["count"] for s in subs if s["difficulty"] == "All"), 0)
        if total == 0:
            total = sum(s["count"] for s in subs)
        return str(total) if total else "N/A"
    except Exception as e:
        print(f"LeetCode fetch failed: {e}")
        return "Error"

async def main_loop():
    os.system("cls" if platform.system() == "Windows" else "clear")
    print(f"{Fore.GREEN}[+] Starting as {username} ({userid})")
    print(f"{Fore.CYAN}[i] LeetCode: {LEETCODE_USERNAME} | Updates every ~30 min")

    while True:
        try:
            async with websockets.connect(
                "wss://gateway.discord.gg/?v=9&encoding=json",
                max_size=None,
                ping_interval=30,
                ping_timeout=20
            ) as ws:
                hello = json.loads(await ws.recv())
                hb_interval = hello["d"]["heartbeat_interval"] / 1000
                print(f"{Fore.CYAN}[DEBUG] Connected - HB every {hb_interval:.0f}s")

                # Identify once
                await ws.send(json.dumps({
                    "op": 2,
                    "d": {
                        "token": usertoken,
                        "properties": {
                            "$os": platform.system(),
                            "$browser": "Discord Client",
                            "$device": "desktop"
                        },
                        "presence": {"status": DISCORD_STATUS, "afk": False},
                        "compress": False
                    }
                }))
                print(f"{Fore.CYAN}[DEBUG] Identify sent")

                last_update = 0
                seq = None

                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=hb_interval + 5)
                        data = json.loads(msg)
                        op = data["op"]

                        if op == 0:  # Dispatch (READY, etc.)
                            if data["t"] == "READY":
                                print(f"{Fore.GREEN}[+] READY - Authenticated!")
                            seq = data.get("s", seq)
                        elif op == 1:  # Heartbeat request
                            await ws.send(json.dumps({"op": 1, "d": seq}))
                        elif op == 11:  # HB ACK
                            pass

                        # Update status every ~30 min
                        if time.time() - last_update > 1800:
                            solved = get_leetcode_solved()
                            custom_text = f"LeetCode Solved: {solved} 🔥"
                            await ws.send(json.dumps({
                                "op": 3,
                                "d": {
                                    "since": 0,
                                    "activities": [{"type": 4, "state": custom_text, "name": "Custom Status", "id": "custom"}],
                                    "status": DISCORD_STATUS,
                                    "afk": False
                                }
                            }))
                            print(f"{Fore.GREEN}[+] Updated status: {custom_text}")
                            last_update = time.time()

                    except asyncio.TimeoutError:
                        # Send heartbeat
                        await ws.send(json.dumps({"op": 1, "d": seq}))
                        print(f"{Fore.CYAN}[HB] Sent")

        except websockets.exceptions.ConnectionClosed as e:
            if e.code == 4004:
                print(f"{Fore.RED}!!! 4004 - Token/session invalidated by Discord !!!")
                print("Action: Get fresh token from browser DevTools → update Render → redeploy")
                await asyncio.sleep(300)  # Wait longer before retry
            else:
                print(f"{Fore.YELLOW}Disconnected ({e.code}): {e.reason}. Reconnecting...")
            await asyncio.sleep(10 + random.randint(0, 20))  # Jitter

        except Exception as e:
            print(f"{Fore.RED}Unexpected error: {e}")
            await asyncio.sleep(60)

keep_alive()
asyncio.run(main_loop())