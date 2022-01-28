# AppX Backend


## Local E2E tests
- run main
- connect with appx or mock project
- `curl -X POST 127.0.0.1:8443/handshake?cc=N/A`
- receive port as response
- use the port as socks proxy:
```
curl --socks5 127.0.0.1:$PORT ipinfo.io
```

## Install for development
- pip install -r requirements.txt
- dist infrastructure project
- pip install infrastructure
- start mongo



## App and backend communication - sequence diagram
![alt text](https://www.websequencediagrams.com/cgi-bin/cdraw?lz=dGl0bGUgUmV2ZXJzZSBzb2NrcyBwcm94eQpwYXJ0aWNpcGFudCBBbmRyb2lkIGFzIEEADA1TZXJ2ZXIgYXMgUwoKQS0-Uzogb3BlbiB0Y3AgY29ubmVjdGlvbgATB3NlbmQgaW1laSxmY21fdG9rZW4KUy0-QTogYXV0aGVudGljYXRpb24gbWV0aG9kcwBKB3BpY2tzAA0WADgHdXNlciAmIHBhc3N3b3JkAIECB2FwcHJvdmVkIC8gZGVuaWUAJggAgREHIHJlcXVlc3QgKGlwLCBwb3J0KQCBIAh1Y2VzcyAvIGZhaWwKCmxvb3Agd2hpbGUAgUsIZWQKICAgIACBNgYAgVEFcGFja2V0ABEFQQCBTQV0cmFuc2ZlciB0byB0YXJnABMKUwATCnMgcmVzcG9uc2UKZW5kCg&s=napkin)


source:
```
title Reverse socks proxy
participant Android as A
participant Server as S

A->S: open tcp connection
A->S: send imei,fcm_token
S->A: authentication methods
A->S: picks authentication method
S->A: user & password
A->S: approved / denied
S->A: connect request (ip, port)
A->S: sucess / fail

loop while connected
    S->A: send packet
    A->A: transfer to target
    A->S: transfers response
end
```
