import requests
import urllib3

# Optional: suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def login_to_gsccca(username: str, password: str) -> requests.Session:
    """
    Logs in to the GSCCCA website and returns an authenticated session.
    
    Args:
        username (str): Your GSCCCA username.
        password (str): Your GSCCCA password.
    
    Returns:
        session (requests.Session): Authenticated session for further requests.
    
    Raises:
        Exception: If login fails or session is invalid.
    """
    session = requests.Session()

    login_url = "https://www.gsccca.org/api/auth/login"
    payload = {
        "name": username,
        "pass": password,
        "captcha": "",
        "verifyCaptcha": False
    }

    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.gsccca.org",
        "Referer": "https://www.gsccca.org/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    }

    # Send login request
    response = session.post(login_url, headers=headers, json=payload, verify=False)

    if response.status_code != 200:
        raise Exception(f"Login failed: HTTP {response.status_code}")

    data = response.json()
    if not data.get("loginStatus"):
        raise Exception(f"Login failed: {data.get('statusMessage')}")

    return session
