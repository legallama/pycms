import urllib.request
try:
    r = urllib.request.urlopen("http://127.0.0.1:5000/admin/")
    print(r.getcode())
    print(r.read().decode()[:300])
except Exception as e:
    print(f"ERROR: {e}")
