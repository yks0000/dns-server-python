## Install Package

```bash
pip3.9 install -r requirements.txt
```

## Start DNS Server

Default port: 5053

```bash
python3.9 main.py
```

## Test

```bash
nslookup -port=5053 -type=CNAME blog.example.com localhost
```

## Update/Add Records

Update records in `zones/example.com.json`. The change in zone file will auto reloaded.


## Notes

Support only one zone.