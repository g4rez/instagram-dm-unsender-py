#!/usr/bin/env python3

# Author: Ensar
# License: MIT (See LICENSE file for details)

import os
import sys

# Prevent __pycache__ directory from being created
sys.dont_write_bytecode = True

import json
import time
import unicodedata
import re
import threading
import concurrent.futures
from datetime import datetime
from typing import Any, Dict, List, Optional

# Best-effort: make Windows console UTF-8 to avoid UnicodeEncodeError on emojis/symbols.
if os.name == "nt":
    try:
        os.system("chcp 65001 >nul")
    except Exception:
        pass
try:
    # Python 3.7+: available on TextIOWrapper
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

if sys.version_info < (3, 9):
    print("ERROR: Python 3.9 or higher required (instagrapi requirement)")
    sys.exit(1)

try:
    from instagrapi import Client
except ImportError as e:
    print(f"ERROR: instagrapi not installed: {e}")
    print("Install with: pip install instagrapi")
    sys.exit(1)

def _default_session_path() -> str:
    """
    Prefer local session.json for portability, but keep a writable fallback under user profile.
    This avoids failing login when the working directory is restricted/locked.
    """
    local = os.path.join(os.getcwd(), "session.json")
    if os.path.exists(local):
        return local
    appdata = os.getenv("APPDATA")
    base = appdata if appdata else os.path.expanduser("~")
    return os.path.join(base, "Ensar", "session.json")


def _fallback_session_path() -> str:
    appdata = os.getenv("APPDATA")
    base = appdata if appdata else os.path.expanduser("~")
    return os.path.join(base, "Ensar", "session.json")


def _session_candidates() -> List[str]:
    """
    Check both local and fallback paths so auto-login works
    even if previous run saved session to fallback.
    """
    local = os.path.join(os.getcwd(), "session.json")
    fallback = _fallback_session_path()
    if os.path.abspath(local) == os.path.abspath(fallback):
        return [local]
    return [local, fallback]


SESSION_FILE = _default_session_path()


def _ensure_session_dir(session_file: str) -> None:
    d = os.path.dirname(os.path.abspath(session_file))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def normalize_text(text):
    if not text: return ""
    text = text.lower()
    text = ''.join(c for c in unicodedata.normalize('NFD', text)
                  if unicodedata.category(c) != 'Mn')
    return text.replace('ς', 'σ')

def get_password():
    """Get password input"""
    try:
        import getpass
        return getpass.getpass("Instagram password (hidden): ")
    except Exception:
        print("Note: Password will be visible")
        return input("Instagram password: ")

def load_session(client: Client, session_file: str) -> bool:
    """Load session"""
    if not os.path.exists(session_file):
        return False
    try:
        client.load_settings(session_file)
        client.account_info()
        return True
    except:
        try:
            os.remove(session_file)
        except:
            pass
        return False

def save_session(client: Client, session_file: str) -> bool:
    """Save session"""
    try:
        client.dump_settings(session_file)
        return True
    except:
        return False

class Color:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    WHITE = '\033[97m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    
class IGDMTool:
    def __init__(self):
        self.client = Client()
        self.logged_in = False
        os.system('')
        self.session_file = SESSION_FILE
        self.selected_thread_id = None
        self.selected_thread_ids = None  # when set, operations apply to all threads
        self.my_username = None
        self.my_user_id = None
        self.selected_username = "None"
        self.last_matches = []
        # Speed tuning (safer defaults; adjustable from menu)
        self.fetch_page_limit = 500          # API page size for fetching thread items
        self.scan_page_sleep_s = 0.0        # sleep between page fetches
        self.scan_ui_sleep_s = 0.0        # tiny sleep during scan UI updates
        self.delete_sleep_s = 0.0           # sleep between delete requests
        self._try_auto_login_on_start()

    def _extract_sender_id(self, item: Dict[str, Any]) -> Optional[str]:
        """Best-effort sender extraction across different DM item payload shapes."""
        for k in ("user_id", "sender_id", "from_user_id", "owner_id"):
            v = item.get(k)
            if v is not None:
                return str(v)
        user_obj = item.get("user") or {}
        pk = user_obj.get("pk")
        if pk is not None:
            return str(pk)
        return None

    def _extract_item_id(self, item: Dict[str, Any]) -> Optional[str]:
        """Best-effort item id extraction for delete endpoint/method."""
        for k in ("item_id", "id", "pk"):
            v = item.get(k)
            if v:
                return str(v)
        return None

    def _try_auto_login_on_start(self) -> bool:
        """Try auto-login from saved session when app starts."""
        for candidate in _session_candidates():
            if not os.path.exists(candidate):
                continue
            try:
                self.client.load_settings(candidate)
                info = self.client.account_info()
                self.my_username = info.username
                self.my_user_id = str(info.pk)
                self.session_file = candidate
                self.logged_in = True
                return True
            except Exception:
                try:
                    os.remove(candidate)
                except Exception:
                    pass
                continue
        return False

    def fetch_all_threads_paginated(self, max_threads: int = 5000) -> List[Dict[str, Any]]:
        threads: List[Dict[str, Any]] = []
        cursor = None
        while len(threads) < max_threads:
            params = {"persistent_badging": "true", "limit": str(self.fetch_page_limit)}
            if cursor:
                params["cursor"] = cursor
            response = self.client.private_request("direct_v2/inbox/", params=params)
            inbox = response.get("inbox", {})
            new_threads = inbox.get("threads", []) or []
            if not new_threads:
                break
            threads.extend(new_threads)
            cursor = inbox.get("oldest_cursor")
            if not cursor:
                break
            if self.scan_page_sleep_s > 0:
                time.sleep(self.scan_page_sleep_s)
        return threads

    def speed_settings(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Color.PURPLE}{'='*60}{Color.END}")
        print(f"{Color.BOLD}{Color.CYAN}          ⚡ SPEED / SAFETY SETTINGS{Color.END}")
        print(f"{Color.PURPLE}{'='*60}{Color.END}\n")

        print(f"{Color.BOLD}Current settings:{Color.END}")
        print(f" - Fetch page limit:   {Color.YELLOW}{self.fetch_page_limit}{Color.END}")
        print(f" - Scan page sleep:    {Color.YELLOW}{self.scan_page_sleep_s:.3f}s{Color.END}")
        print(f" - Scan UI sleep:      {Color.YELLOW}{self.scan_ui_sleep_s:.3f}s{Color.END}")
        print(f" - Delete sleep:       {Color.YELLOW}{self.delete_sleep_s:.3f}s{Color.END}\n")

        print(f"{Color.BOLD}[1]{Color.END} Normal (recommended)")
        print(f"{Color.BOLD}[2]{Color.END} FAST (more risk of rate-limit/lock)")
        print(f"{Color.BOLD}[3]{Color.END} Custom")
        print(f"{Color.BOLD}[ENTER]{Color.END} Back\n")

        choice = input(f"{Color.BOLD}Selection > {Color.END}").strip()

        if choice == "1":
            self.fetch_page_limit = 500
            self.scan_page_sleep_s = 0.0
            self.scan_ui_sleep_s = 0.0
            self.delete_sleep_s = 0.0
            print(f"\n{Color.GREEN}✅ Set to Normal.{Color.END}")
            time.sleep(0.1)
            return

        if choice == "2":
            # Aggressive but still non-zero delays to reduce immediate lockouts
            self.fetch_page_limit = 500
            self.scan_page_sleep_s = 0.0
            self.scan_ui_sleep_s = 0.0
            self.delete_sleep_s = 0.0
            print(f"\n{Color.YELLOW}⚠️ Set to FAST. Use at your own risk.{Color.END}")
            time.sleep(0.1)
            return

        if choice == "3":
            def ask_int(prompt: str, vmin: int, vmax: int, current: int) -> int:
                raw = input(f"{prompt} ({vmin}-{vmax}) [current {current}]: ").strip()
                if not raw:
                    return current
                try:
                    v = int(raw)
                except:
                    return current
                return max(vmin, min(vmax, v))

            def ask_float(prompt: str, vmin: float, vmax: float, current: float) -> float:
                raw = input(f"{prompt} ({vmin}-{vmax}) [current {current}]: ").strip()
                if not raw:
                    return current
                try:
                    v = float(raw)
                except:
                    return current
                return max(vmin, min(vmax, v))

            print(f"\n{Color.CYAN}Leave blank to keep current value.{Color.END}\n")
            self.fetch_page_limit = ask_int("Fetch page limit", 25, 1000, self.fetch_page_limit)
            self.scan_page_sleep_s = ask_float("Scan page sleep (seconds)", 0.0, 2.0, self.scan_page_sleep_s)
            self.scan_ui_sleep_s = ask_float("Scan UI sleep (seconds)", 0.0, 0.05, self.scan_ui_sleep_s)
            self.delete_sleep_s = ask_float("Delete sleep (seconds)", 0.0, 5.0, self.delete_sleep_s)

            print(f"\n{Color.GREEN}✅ Custom speed settings saved.{Color.END}")
            time.sleep(0.1)
            return
    
    def login(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Color.PURPLE}{'='*50}{Color.END}")
        print(f"{Color.BOLD}{Color.CYAN}          🔐 INSTAGRAM SECURE LOGIN{Color.END}")
        print(f"{Color.PURPLE}{'='*50}{Color.END}\n")

        for candidate in _session_candidates():
            if not os.path.exists(candidate):
                continue
            print(f"{Color.YELLOW}⏳ An existing session was detected. Login...{Color.END}")
            try:
                self.client.load_settings(candidate)
                info = self.client.account_info()
                self.my_username = info.username
                self.my_user_id = str(info.pk)
                self.session_file = candidate
                print(f"\n{Color.GREEN}✅ Welcome back, {Color.BOLD}{self.my_username}!{Color.END}")
                self.logged_in = True
                time.sleep(0.1)
                return True
            except Exception:
                # Corrupted/expired session file; remove and continue with others
                try:
                    os.remove(candidate)
                except Exception:
                    pass
                continue

        user = input(f"{Color.BOLD}Username: {Color.END}").strip()
        pwd = input(f"{Color.BOLD}Password: {Color.END}").strip()
        
        print(f"\n{Color.CYAN}📡 Contact Instagram Servers...{Color.END}")
        
        try:
            self.client.login(user, pwd)
            info = self.client.account_info()
            self.my_username = info.username
            self.my_user_id = str(info.pk)
            self.logged_in = True
            print(f"\n{Color.GREEN}✅ LOGIN SUCCESSFUL!{Color.END}")
            print(f"{Color.BLUE}User ID: {self.my_user_id}{Color.END}")
            # Session persistence should never make login "fail"
            try:
                _ensure_session_dir(self.session_file)
                self.client.dump_settings(self.session_file)
            except Exception as e:
                # Try fallback path under APPDATA/home if local file is locked or denied
                try:
                    fallback = _fallback_session_path()
                    _ensure_session_dir(fallback)
                    self.client.dump_settings(fallback)
                    self.session_file = fallback
                    print(f"{Color.YELLOW}⚠️ Could not write session to '{SESSION_FILE}'. Saved to '{fallback}' instead.{Color.END}")
                except Exception:
                    print(f"{Color.YELLOW}⚠️ Session could not be saved (permission/lock). You can still use the tool, but you'll need to login again next time.{Color.END}")
            time.sleep(0.1)
        except Exception as e:
            print(f"\n{Color.RED}❌ LOGIN FAILED: {e}{Color.END}")
            input(f"\nPress [ENTER] to retry again...")
            
    def list_threads_raw_api(self):
        if not self.logged_in: 
            print(f"{Color.RED}❌ You must first log in (1)!{Color.END}")
            time.sleep(0.1); return False

        os.system('cls' if os.name == 'nt' else 'clear')
        all_threads = []
        cursor = None
        
        while True:
            print(f"{Color.PURPLE}{'='*65}{Color.END}")
            print(f"{Color.BOLD}{Color.CYAN}          📩 FULL DIRECT MESSAGES LIST{Color.END}")
            print(f"{Color.PURPLE}{'='*65}{Color.END}")
            print(f"{Color.BOLD}{'#':<3} | {'USERNAME':<15} | {'THREAD ID':<22}{Color.END}")
            print(f"{Color.PURPLE}{'-'*65}{Color.END}")

            try:
                params = {"persistent_badging": "true"}
                if cursor:
                    params["cursor"] = cursor
                
                response = self.client.private_request("direct_v2/inbox/", params=params)
                inbox = response.get('inbox', {})
                new_threads = inbox.get('threads', [])
                all_threads.extend(new_threads)
                
                for i, t in enumerate(all_threads, 1):
                    t_id = t.get('thread_id')
                    users = t.get('users', [])
                    username = users[0].get('username', 'Unknown') if users else "Group/Saved"
                    
                    row_color = Color.WHITE if i % 2 == 0 else Color.CYAN
                    print(f"{Color.BOLD}{i:<3}{Color.END} | "
                          f"{row_color}{username[:15]:<15}{Color.END} | "
                          f"{Color.YELLOW}{t_id:<22}{Color.END}")

                print(f"{Color.PURPLE}{'='*65}{Color.END}")
                
                cursor = inbox.get('oldest_cursor')
                
                prompt = f"\n{Color.BOLD}Select #, write 'M' for more, type 'ALL' for all, or [ENTER] for back: {Color.END}"
                choice = input(prompt).strip().lower()

                if choice == "all":
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"{Color.YELLOW}⏳ Collecting all direct message threads...{Color.END}")
                    try:
                        threads = self.fetch_all_threads_paginated()
                        self.selected_thread_ids = [t.get("thread_id") for t in threads if t.get("thread_id")]
                        self.selected_thread_id = None
                        self.selected_username = "ALL"
                        print(f"\n{Color.GREEN}✅ SELECTED ALL THREADS: {Color.BOLD}{len(self.selected_thread_ids)}{Color.END}")
                        time.sleep(0.1)
                        return True
                    except Exception as e:
                        print(f"\n{Color.RED}❌ ERROR FETCHING ALL THREADS: {e}{Color.END}")
                        input(f"\nPress [ENTER] to go back...")
                        return False

                if choice == 'm' and cursor:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"{Color.YELLOW}⏳ Loading next list of direct messages...{Color.END}")
                    continue
                
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(all_threads):
                        self.selected_thread_id = all_threads[idx].get('thread_id')
                        self.selected_thread_ids = None
                        users = all_threads[idx].get('users', [])
                        self.selected_username = users[0].get('username', 'Unknown') if users else "Group"
                        
                        print(f"\n{Color.GREEN}✅ CHOOSEN: {Color.BOLD}{self.selected_username}{Color.END}")
                        time.sleep(0.1)
                        return True
                    else:
                        print(f"{Color.RED}✗ Invalid choice.{Color.END}")
                        time.sleep(0.1)
                else:
                    return False

            except Exception as e:
                print(f"\n{Color.RED}❌ ERROR INBOX: {e}{Color.END}")
                input(f"\nPress [ENTER] to go to the previous list...")
                return False
                
    def select_thread(self):
        if not self.logged_in: 
            print(f"{Color.RED}❌ You must first log in (Option 1)!{Color.END}")
            time.sleep(0.1)
            return

        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Color.PURPLE}{'='*50}{Color.END}")
        print(f"{Color.BOLD}{Color.CYAN}          🎯 TARGET SELECTION (THREAD){Color.END}")
        print(f"{Color.PURPLE}{'='*50}{Color.END}\n")

        name = input(f"{Color.BOLD}Enter the recipient's Username: {Color.END}").strip().lower()
        print(f"\n{Color.YELLOW}🔍 Search for a chat for the user: {Color.BOLD}{name}...{Color.END}")

        try:
            user_id = self.client.user_id_from_username(name)
            
            threads = self.client.direct_threads(30)
            found_thread = None
            
            for t in threads:
                if str(user_id) in [str(u.pk) for u in t.users]:
                    found_thread = t
                    break

            if found_thread:
                self.selected_thread_id = found_thread.id
                self.selected_thread_ids = None
                print(f"\n{Color.GREEN}✅ TARGET FOUND!{Color.END}")
                print(f"{Color.BLUE}Thread ID: {self.selected_thread_id}{Color.END}")
                print(f"{Color.CYAN}Chat with: {name}{Color.END}")
                time.sleep(0.1)
            else:
                print(f"{Color.YELLOW}⚠️ The conversation was not found in recent. Attempting to recover...{Color.END}")
                thread = self.client.direct_thread_by_participants([user_id])
                self.selected_thread_id = getattr(thread, 'id', None) or thread.get('thread_id')
                self.selected_thread_ids = None
                print(f"\n{Color.GREEN}✅ TARGET LOCKED: {self.selected_thread_id}{Color.END}")
                time.sleep(0.1)

        except Exception as e:
            print(f"\n{Color.RED}❌ ERROR TRACKING: {e}{Color.END}")
            input(f"\nPress [ENTER] to go to the menu...")

    def fetch_all_messages_paginated(self, max_messages=5000, thread_id: Optional[str] = None):
        all_messages = []
        cursor = None
        page = 1
        tid = thread_id or self.selected_thread_id
        if not tid:
            return all_messages
        while len(all_messages) < max_messages:
            params = {
                # "unseen" can omit certain item types; "all" is safer for full-history scans
                "visual_message_return_type": "all",
                "direction": "older",
                "limit": str(self.fetch_page_limit),
            }
            if cursor: params["cursor"] = cursor
            response = self.client.private_request(f"direct_v2/threads/{tid}/", params=params)
            thread = response['thread']
            items = thread.get('items', [])
            if not items: break
            all_messages.extend(items)
            cursor = thread.get('oldest_cursor') or thread.get('next_cursor')
            if not cursor: break
            if self.scan_page_sleep_s > 0:
                time.sleep(self.scan_page_sleep_s)
            page += 1
        return all_messages

    def view_messages_raw_api(self):
        if self.selected_thread_ids:
            print(f"{Color.YELLOW}⚠️ 'View Recent Messages' is not available for ALL threads. Select a single conversation first.{Color.END}")
            time.sleep(0.1); return
        if not self.selected_thread_id:
            print(f"{Color.RED}❌ You must first choose a conversation (2 or 3)!{Color.END}")
            time.sleep(0.1); return

        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Color.PURPLE}{'='*60}{Color.END}")
        print(f"{Color.BOLD}{Color.CYAN}          💬 RECENT MESSAGES{Color.END}")
        print(f"{Color.PURPLE}{'='*60}{Color.END}")

        try:
            # Παίρνουμε τα τελευταία 50 μηνύματα
            items = self.fetch_all_messages_paginated(50)
            
            if not items:
                print(f"{Color.YELLOW}No messages were found in this conversation.{Color.END}")
            
            for item in reversed(items):
                user_id = str(item.get('user_id'))
                text = item.get('text', '')
                i_type = item.get('item_type')
                
                prefix = f"{Color.GREEN}[{self.my_username}]{Color.END}" if user_id == self.my_user_id else f"{Color.YELLOW}[{self.selected_username}]{Color.END}"
                
                if i_type == 'text':
                    content = text
                elif i_type == 'clip':
                    content = f"{Color.PURPLE}[REEL]{Color.END}"
                elif i_type == 'voice_media':
                    content = f"{Color.BLUE}[VOICE MESSAGE]{Color.END}"
                elif i_type in ['media', 'visual_media']:
                    content = f"{Color.CYAN}[PHOTO/VIDEO]{Color.END}"
                else:
                    content = f"{Color.WHITE}[{i_type.upper()}]{Color.END}"

                print(f"{prefix}: {content}")

            print(f"{Color.PURPLE}{'='*60}{Color.END}")
            
            input(f"\n{Color.BOLD}Press [ENTER] to go to the main menu...{Color.END}")

        except Exception as e:
            print(f"\n{Color.RED}❌ ERROR: {e}{Color.END}")
            input(f"\nPress [ENTER] to go back...")

    def search_messages_raw_api(self):
        if not self.selected_thread_id and not self.selected_thread_ids:
            print(f"{Color.RED}❌ You must first choose a conversation (2)!{Color.END}")
            input(f"\nPress [ENTER] to go back...")
            return False

        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Color.PURPLE}{'='*60}{Color.END}")
        print(f"{Color.BOLD}{Color.CYAN}          📡 FULL SCAN OF MESSAGES{Color.END}")
        print(f"{Color.PURPLE}{'='*60}{Color.END}")
        print(f"{Color.YELLOW}🔍 Start scan... Please wait.{Color.END}\n")

        self.last_matches = []
        
        # Counters
        count_text = 0
        count_media = 0
        count_reels = 0
        count_voice = 0
        count_other = 0
        
        print(f"{Color.BOLD}DATA ASSSIS:{Color.END}")
        print(f"{Color.PURPLE}{'-'*30}{Color.END}")

        def process_items(items_to_process: List[Dict[str, Any]]):
            nonlocal count_text, count_media, count_reels, count_voice, count_other
            for item in items_to_process:
                t = item.get('text', '')
                it = item.get('item_type')
                it = it or ""
                
                is_text = (it == 'text')
                # Reels / post shares / story shares often come as different item types depending on sender/client
                is_reel = (it in ['clip', 'animated_media', 'reel_share'] or 'clip' in item)
                is_voice = (it == 'voice_media' or 'voice_media' in item)
                # Media can appear under several item types depending on how it was sent
                is_media = (it in ['media', 'visual_media', 'raven_media', 'media_share', 'animated_media'] or 'media' in item or 'visual_media' in item)
                # Post link / profile share / story share variants (these were missing before)
                is_share_link = (
                    it in ['link', 'xma_share', 'media_share', 'story_share', 'felix_share', 'user_profile_share', 'profile_share', 'reel_share']
                    or ('share' in it)
                    or ('reel' in it)
                    or ('link' in it)
                )

                # Avoid deleting "system" / action items.
                is_action = (it == 'action_log')

                has_id = bool(self._extract_item_id(item))
                has_user = bool(self._extract_sender_id(item))
                # Allow deleting any message that is not a system action log.
                # This explicitly catches post, reel, and story shares even if their item_type is unknown or weird.
                is_deletable_candidate = (not is_action) and has_id and has_user

                if is_deletable_candidate:
                    self.last_matches.append(item)
                    
                    if is_text: 
                        count_text += 1
                        print(f"{Color.GREEN}✓ [TEXT]{Color.END} {t[:30]}...", end="\r")
                    elif is_reel or is_share_link: 
                        count_reels += 1
                        print(f"{Color.PURPLE}✓ [REEL/POST] Found Share!{Color.END}", end="\r")
                    elif is_voice: 
                        count_voice += 1
                        print(f"{Color.BLUE}✓ [VOICE] Found Ηχητικό!{Color.END}", end="\r")
                    elif is_media: 
                        count_media += 1
                        print(f"{Color.CYAN}✓ [MEDIA] Found Photo/Video!{Color.END}", end="\r")
                    else:
                        count_other += 1
                        label = (it or "unknown").upper()
                        # Keep UI lightweight; don't spam full payloads
                        print(f"{Color.WHITE}✓ [{label}] Found item!{Color.END}", end="\r")
                    
                    if self.scan_ui_sleep_s > 0:
                        time.sleep(self.scan_ui_sleep_s)

        if self.selected_thread_ids:
            tids = self.selected_thread_ids
            total = len(tids)
            completed = 0
            
            def scan_thread(tid):
                try:
                    items_fetch = self.fetch_all_messages_paginated(5000, thread_id=tid)
                    for it in items_fetch:
                        if isinstance(it, dict):
                            it["_thread_id"] = tid
                    return items_fetch
                except Exception:
                    return []

            with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
                futures = {executor.submit(scan_thread, tid): tid for tid in tids}
                for future in concurrent.futures.as_completed(futures):
                    completed += 1
                    print(f"{Color.YELLOW}Scanning thread {completed}/{total}...{Color.END}", end="\r")
                    res_items = future.result()
                    if res_items:
                        process_items(res_items)
        else:
            items = self.fetch_all_messages_paginated(5000)
            process_items(items)

        print(f"\n\n{Color.PURPLE}{'='*60}{Color.END}")
        print(f"{Color.BOLD}{Color.GREEN}✅ The scan is completed!{Color.END}")
        print(f"{Color.PURPLE}{'-'*60}{Color.END}")
        print(f" 📝 Texts:    {Color.BOLD}{count_text}{Color.END}")
        print(f" 🎬 Reels/Posts:  {Color.BOLD}{count_reels}{Color.END}")
        print(f" 🎤 Voice Messages:    {Color.BOLD}{count_voice}{Color.END}")
        print(f" 🖼️ Media:      {Color.BOLD}{count_media}{Color.END}")
        print(f" 🔗 Other (links/shares/etc): {Color.BOLD}{count_other}{Color.END}")
        
        # Some item types may use different field names for sender.
        # We'll keep this count consistent with the deletion logic below.
        own_count = len([m for m in self.last_matches if self._extract_sender_id(m) == self.my_user_id])
        others_count = len(self.last_matches) - own_count

        print(f"\n{Color.PURPLE}{'='*60}{Color.END}")
        print(f" 🚀 {Color.BOLD}ABOUTIONS REFERRING:{Color.END}")
        print(f" {Color.GREEN}Yours (will be deleted): {Color.BOLD}{own_count}{Color.END}")
        print(f" {Color.RED}Other (They will remain): {Color.BOLD}{others_count}{Color.END}")
        print(f"{Color.PURPLE}{'='*60}{Color.END}")
        print(f" 🚀 {Color.BOLD}TOTAL FOR DELETION: {own_count}{Color.END}")
        print(f"{Color.PURPLE}{'='*60}{Color.END}")
        
        print(f"\n{Color.YELLOW}Proceeding to delete messages automatically...{Color.END}")
        time.sleep(0.1)
        return True
                       
    def delete_messages_raw_api(self):
        """Διαγραφή μηνυμάτων με εμφάνιση κειμένου (Live Feedback)"""
        if not self.last_matches: 
            print(f"{Color.RED}❌ There are no messages! Run the Scan first (5).{Color.END}")
            input(f"\nPress [ENTER] to go back...")
            return
        
        own = [m for m in self.last_matches if self._extract_sender_id(m) == self.my_user_id]
        
        if not own:
            print(f"{Color.YELLOW}⚠️ No messages were found for deletion.{Color.END}")
            input(f"\nPress [ENTER] to go back...")
            return

        print(f"\n{Color.PURPLE}{'='*65}{Color.END}")
        print(f"{Color.YELLOW}WILL BE DELETED {Color.BOLD}{len(own)}{Color.END}{Color.YELLOW} MESSAGES.{Color.END}")
        print(f"{Color.BOLD}Type 'yes' to confirm: {Color.END}yes (auto)")
        confirm = 'yes'
        
        if confirm == 'yes':
            print(f"\n{Color.CYAN}🚀 Deletion of messages has been started...{Color.END}\n")
            try:
                print(f"{Color.BOLD}Max items to try delete [default: all]: {Color.END}all (auto)")
                max_raw = ''
                if max_raw:
                    try:
                        max_items = max(1, int(max_raw))
                        own = own[:max_items]
                    except:
                        pass

                print_lock = threading.Lock()
                total_own = len(own)

                def delete_worker(i, m):
                    mid = self._extract_item_id(m)
                    if not mid:
                        with print_lock:
                            print(f"{Color.YELLOW}[{i}/{total_own}] Skipped item (missing id). Type: {m.get('item_type')}{Color.END}")
                        return
                    thread_id = m.get("_thread_id") or self.selected_thread_id
                    if not thread_id:
                        with print_lock:
                            print(f"{Color.YELLOW}[{i}/{total_own}] Skipped item (missing thread id).{Color.END}")
                        return
                    
                    msg_text = m.get('text', '')
                    if not msg_text:
                        msg_text = f"[{m.get('item_type', 'MEDIA').upper()}]"
                    
                    display_text = (msg_text[:30] + '..') if len(msg_text) > 30 else msg_text

                    # Better unsend method: pass original client_context to avoid 403 spam traps
                    deleted = False
                    retries = 0
                    max_retries = 3
                    
                    while retries < max_retries:
                        try:
                            payload_data = {
                                "_uuid": getattr(self.client, "uuid", ""),
                                "_uid": self.my_user_id,
                                "_csrftoken": getattr(self.client, "token", ""),
                            }
                            
                            client_context = m.get("client_context")
                            if client_context:
                                payload_data["client_context"] = client_context
                                payload_data["original_message_client_context"] = client_context
                            else:
                                import uuid
                                new_ctx = str(uuid.uuid4())
                                payload_data["client_context"] = new_ctx
                                payload_data["original_message_client_context"] = new_ctx

                            self.client.private_request(
                                f"direct_v2/threads/{thread_id}/items/{mid}/delete/",
                                data=payload_data
                            )
                            deleted = True
                            break
                        except Exception as e:
                            msg = str(e)
                            if "1545003" in msg or "error_code" in msg and "1545003" in msg:
                                time.sleep(15)
                                retries += 1
                                deleted = False
                            else:
                                with print_lock:
                                    print(f"{Color.YELLOW}[{i}/{total_own}] Delete failed. Type={m.get('item_type')} mid={mid[-6:]}{Color.END}")
                                    print(f"{Color.YELLOW}Details:{Color.END} {msg[:100]}")
                                deleted = False
                                break

                    mid_str = str(mid)
                    if deleted:
                        with print_lock:
                            print(f"{Color.GREEN}[{i}/{total_own}]{Color.END} {Color.WHITE}ID: {mid_str[-6:]}{Color.END} | {Color.CYAN}{display_text} -> DELETED{Color.END}")
                    
                    if self.delete_sleep_s > 0:
                        time.sleep(self.delete_sleep_s)

                with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
                    futures = [executor.submit(delete_worker, i, m) for i, m in enumerate(own, 1)]
                    concurrent.futures.wait(futures)
                
                print(f"\n{Color.GREEN}✨ Mission Finished successfully!{Color.END}")
                input("\nPress [ENTER] to go back...")
                
            except KeyboardInterrupt:
                print(f"\n\n{Color.YELLOW}🛑 PROCEDURE CONTROL BY THE USER.{Color.END}")
                time.sleep(0.1)
            except Exception as e:
                print(f"\n{Color.RED}❌ ERROR: {e}{Color.END}")
                time.sleep(0.1)
        else:
            print(f"\n{Color.WHITE}The deletion has been canceled.{Color.END}")
            time.sleep(0.1)
            
        self.last_matches = []
    
    def logout(self):
        """Αποσύνδεση και καθαρισμός Session στην επιλογή 8"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Color.PURPLE}{'='*50}{Color.END}")
        print(f"{Color.BOLD}{Color.RED}          🚪 Logout / Switch instagram account{Color.END}")
        print(f"{Color.PURPLE}{'='*50}{Color.END}\n")
        
        confirm = input(f"{Color.YELLOW}You want to log out of the account {self.my_username}; (y/n): {Color.END}").lower()
        
        if confirm == 'y':
            # Delete saved sessions from known locations
            deleted_any = False
            for s in _session_candidates():
                if os.path.exists(s):
                    try:
                        os.remove(s)
                        deleted_any = True
                    except Exception:
                        pass
            if deleted_any:
                print(f"{Color.GREEN}✅ The session has been deleted.{Color.END}")
            
            self.client = Client()
            self.logged_in = False
            self.my_username = "None"
            self.my_user_id = None
            self.selected_thread_id = None
            self.selected_thread_ids = None
            self.selected_username = "None"
            
            print(f"\n{Color.CYAN}Ready to login with different account (Option 1).{Color.END}")
            time.sleep(0.1)
            
    def menu_loop(self):
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"{Color.BOLD}{Color.YELLOW}  /$$$$$$                                         {Color.END}")
            print(f"{Color.BOLD}{Color.GREEN} /$$__  $$                                        {Color.END}")
            print(f"{Color.BOLD}{Color.CYAN}| $$  \\__/  /$$$$$$   /$$$$$$   /$$$$$$  /$$$$$$$${Color.END}")
            print(f"{Color.BOLD}{Color.BLUE}| $$ /$$$$ |____  $$ /$$__  $$ /$$__  $$|____ /$$/{Color.END}")
            print(f"{Color.BOLD}{Color.PURPLE}| $$|_  $$  /$$$$$$$| $$  \\__/| $$$$$$$$   /$$$$/ {Color.END}")
            print(f"{Color.BOLD}{Color.RED}| $$  \\ $$ /$$__  $$| $$      | $$_____/  /$$__/  {Color.END}")
            print(f"{Color.BOLD}{Color.YELLOW}|  $$$$$$/|  $$$$$$$| $$      |  $$$$$$$ /$$$$$$$${Color.END}")
            print(f"{Color.BOLD}{Color.GREEN} \\______/  \\_______/|__/       \\_______/|________/{Color.END}")
            print(f"{Color.PURPLE}{'='*50}{Color.END}")
            
            status = f"{Color.GREEN}Connected as: {self.my_username}" if self.logged_in else f"{Color.RED}Status: Not Logged In"
            print(f" {status}{Color.END}")
            if self.selected_thread_ids:
                target_display = f"{Color.YELLOW}ALL{Color.END} ({Color.WHITE}{len(self.selected_thread_ids)} threads{Color.END})"
            else:
                target_display = f"{Color.YELLOW}{self.selected_username}{Color.END} ({Color.WHITE}{self.selected_thread_id}{Color.END})" if self.selected_thread_id else f"{Color.RED}None{Color.END}"
            print(f" 🎯 TARGET: {target_display}")
            
            print(f"{Color.PURPLE}{'-'*50}{Color.END}")
            print(f" {Color.BOLD}[1]{Color.END} Login Account")
            print(f" {Color.BOLD}[2]{Color.END} Full Direct Messages List")
            print(f" {Color.BOLD}[3]{Color.END} Select Target by Username/ID")
            print(f" {Color.BOLD}[4]{Color.END} View Recent Messages")
            print(f" {Color.BOLD}[5]{Color.END} {Color.CYAN}Start a full scan of all messages{Color.END}")
            print(f" {Color.BOLD}[6]{Color.END} {Color.RED}Delete all messages sent{Color.END}")
            print(f" {Color.BOLD}[7]{Color.END} Logout / Switch instagram account")
            print(f" {Color.BOLD}[8]{Color.END} Exit")
            print(f" {Color.BOLD}[9]{Color.END} Speed / Safety settings")
            print(f"{Color.PURPLE}{'='*50}{Color.END}")
            
            choice = input(f"\n{Color.BOLD}Selection > {Color.END}").strip()
            
            if choice == "1": self.login()
            elif choice == "2":
                if self.list_threads_raw_api():
                    self.search_messages_raw_api()
                    self.delete_messages_raw_api()
            elif choice == "3": self.select_thread()
            elif choice == "4": self.view_messages_raw_api()
            elif choice == "5":
                if self.search_messages_raw_api():
                    self.delete_messages_raw_api()
            elif choice == "6": self.delete_messages_raw_api()
            elif choice == "7": self.logout()
            elif choice == "8": 
                print(f"{Color.YELLOW}Exiting... Fly safe! 🚀{Color.END}")
                break
            elif choice == "9": self.speed_settings()

if __name__ == "__main__":
    try:
        tool = IGDMTool()
        tool.menu_loop()
    except KeyboardInterrupt:
        print(f"\n\n{Color.YELLOW}👋 Bye! The missile landed safely.{Color.END}")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

# ==========================================
# OTHER SCRIPTS MERGED BELOW FOR REFERENCE
# ==========================================
"""
# --- check_user.py ---
import json
from instagrapi import Client

try:
    c = Client()
    c.load_settings("session.json")
    print("My User ID:", c.user_id)
except Exception as e:
    print("Error:", e)


# --- find_reels.py ---
import json
from instagrapi import Client

try:
    c = Client()
    c.load_settings("session.json")
    my_user = str(c.user_id)
    resp = c.private_request("direct_v2/inbox/", params={"limit": 100})
    threads = resp.get("inbox", {}).get("threads", [])
    
    collected = []
    for t in threads:
        tid = t.get("thread_id")
        t_resp = c.private_request(f"direct_v2/threads/{tid}/", params={"limit": 50})
        for item in t_resp.get("thread", {}).get("items", []):
            itype = item.get("item_type", "")
            sender = str(item.get("user_id") or item.get("sender_id"))
            if sender == my_user and (itype in ("clip", "media_share", "xma_share", "story_share") or "share" in itype or "clip" in item or "media_share" in item):
                collected.append({
                    "item_type": itype,
                    "item_id": item.get("item_id"),
                    "id": item.get("id"),
                    "sender_id": sender,
                    "full_keys": list(item.keys()),
                    "original_item": item,
                })
                if len(collected) >= 5:
                    break
        if len(collected) >= 5:
            break
            
    with open("my_reels.json", "w", encoding="utf-8") as f:
        json.dump(collected, f, indent=2, ensure_ascii=False)
    print("Saved my_reels.json")
except Exception as e:
    print("Error:", e)


# --- debug.py ---
import json
from x import IGDMTool

tool = IGDMTool()
tool.my_user_id = "58647140679"  # Dummy ID from reels_out.json
with open("reels_out.json", "r") as f:
    items = json.load(f)

for m in items:
    print(m["item_type"])
    print("Item ID:", tool._extract_item_id(m))
    print("Sender ID:", tool._extract_sender_id(m))
    print("Is own?", tool._extract_sender_id(m) == tool.my_user_id)


# --- debug2.py ---
import json
from x import IGDMTool

tool = IGDMTool()
with open("test_out.json", "r") as f:
    items = json.load(f)

missing = []
for m in items:
    id_ = tool._extract_item_id(m)
    uid_ = tool._extract_sender_id(m)
    if not id_ or not uid_:
        missing.append(m.get('item_type'))
        
print("Items missing ID or UID count:", len(missing))
print("Item types:", set(missing))


# --- test_fetch.py ---
import json
from instagrapi import Client

try:
    c = Client()
    c.load_settings("session.json")
    resp = c.private_request("direct_v2/inbox/", params={"limit": 5})
    threads = resp.get("inbox", {}).get("threads", [])
    
    collected = []
    for t in threads[:2]:
        tid = t.get("thread_id")
        t_resp = c.private_request(f"direct_v2/threads/{tid}/", params={"limit": 20})
        for item in t_resp.get("thread", {}).get("items", []):
            collected.append({
                "item_type": item.get("item_type"),
                "item_id": item.get("item_id"),
                "id": item.get("id"),
                "sender_id": item.get("user_id") or item.get("sender_id"),
                "full_keys": list(item.keys()),
                # store some details if it is a clip or media share
                "is_clip": "clip" in item,
                "is_media_share": "media_share" in item,
                "is_xma": "xma_share" in item,
            })
    
    with open("test_out.json", "w") as f:
        json.dump(collected, f, indent=2)
    print("Saved test_out.json")
except Exception as e:
    print("Error:", e)
"""
