import urllib.request
try:
    r = urllib.request.urlopen("http://127.0.0.1:5000/admin/")
    print(r.getcode())
    print(r.read().decode())
except Exception as e:
    print(f"ERROR: {e}")
    if hasattr(e, "read"):
        print(e.read().decode())
