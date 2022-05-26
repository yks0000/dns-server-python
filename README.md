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


Example:

```bash
nslookup -port=5053 -type=CNAME blog.example.com localhost
Server:		localhost
Address:	127.0.0.1#5053

blog.example.com	canonical name = github.io.
Name:	github.io
Address: 185.199.108.153
Name:	github.io
Address: 185.199.109.153
Name:	github.io
Address: 185.199.110.153
Name:	github.io
Address: 185.199.111.153
```

## Update/Add Records

Update records in `zones/example.com.json`. The change in zone file will auto reloaded.


## Notes

Support only one zone.