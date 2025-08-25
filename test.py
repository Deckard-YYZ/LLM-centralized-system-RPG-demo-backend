import socket
import json
import struct
import time
from time import sleep

data = [
{
"intermediatorID": "Celin",
"AttAndRelRCPT": "Arthur the Adventurer",
"AttitudeChange": "Fearful",
"RelationshipTypeChange": "Avoid",
"Rationale": "Seeing Arthur strike Alex violently shocks Celin; she now sees him as dangerous and unpredictable."
},
{
"intermediatorID": "Celin",
"AttAndRelRCPT": "alex",
"AttitudeChange": "Protective",
"RelationshipTypeChange": "Wife of",
"Rationale": "Arthur’s attack reinforces her care and worry for her husband."
},
{
"intermediatorID": "Celin",
"RecipientID": "alex",
"intermediatorStatus": "Rushing to aid",
"RecipientStatus": "Injured",
"intermediatorDialogue": "Alex! Are you alright? Gods, what did he do to you?!",
"RecipientDialogue": "I’ll be fine... just help me inside, love. That man’s mad."
},
{
"intermediatorID": "Celin",
"RecipientID": "Arthur the Adventurer",
"intermediatorStatus": "Terrified",
"RecipientStatus": "Confronted",
"intermediatorDialogue": "You stay away from us! There’s no call for such violence here!",
"RecipientDialogue": "Tch. He asked for it. Mind your own, woman."
}
]

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('127.0.0.1', 7777))
s.listen(1)
print("Server waiting for client...")

conn, addr = s.accept()
print(f"Client connected: {addr}")
sleep(3)
# Send data to client
raw = json.dumps(data, ensure_ascii=False).encode('utf-8') + b'\n'
conn.sendall(raw)
# time.sleep(1)
# raw = json.dumps(data, ensure_ascii=False).encode('utf-8') + b'\n'
# conn.sendall(raw)
# conn.sendall(json.dumps(data, ensure_ascii=False).encode('utf-8'))
print("SENT")

# Keep connection open to receive more data
try:
    while True:
        received_data = conn.recv(1024)
        conn.sendall(raw)
        if not received_data:
            break
        print("Received from client:", received_data.decode())
except KeyboardInterrupt:
    print("Server shutting down.")

conn.close()
s.close()




