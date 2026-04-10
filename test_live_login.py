import urllib.request
import urllib.parse
import http.cookiejar

# Setup cookie jar
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# login
data = urllib.parse.urlencode({"email": "admin@example.com", "password": "pass"}).encode()
try:
    print("Logging in...")
    r = opener.open("http://127.0.0.1:5000/admin/login", data=data)
    print(f"LOGIN CODE: {r.getcode()}")
    
    # Hit dashboard
    print("Getting Dashboard...")
    r = opener.open("http://127.0.0.1:5000/admin/")
    print(f"DASHBOARD CODE: {r.getcode()}")
except Exception as e:
    print(f"ERROR: {e}")
    if hasattr(e, "read"):
        print(e.read().decode())
