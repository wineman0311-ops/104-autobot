"""
Helper: encode corp_auth_state.json to base64 for Zeabur env var.

Run locally:
    py -3.11 encode_auth.py

Then copy the output and paste it as CORP_AUTH_STATE_JSON
in your Zeabur service environment variables.
"""
import base64, os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corp_auth_state.json")

if not os.path.exists(path):
    print("ERROR: corp_auth_state.json not found. Run corp_phase1.py + corp_phase2.py first.")
else:
    content = open(path, "rb").read()
    encoded = base64.b64encode(content).decode("ascii")
    print("=== CORP_AUTH_STATE_JSON (paste into Zeabur env vars) ===")
    print(encoded)
    print(f"\nLength: {len(encoded)} chars")
