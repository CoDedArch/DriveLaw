import secrets
import hashlib

def generate_api_key() -> tuple[str, str]:
    raw_key = secrets.token_hex(32)
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, hashed_key

if __name__ == "__main__":
    raw, hashed = generate_api_key()
    print(f"🔑 RAW KEY (CLIENT): {raw}")
    print(f"🔒 HASHED KEY (SERVER): {hashed}")
    print("\nAdd the hashed key to your .env file as `API_KEY_HASH=...`")