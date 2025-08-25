import socket
import json
import chatClass
import NPCInfoTest
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

NPCmap = NPCInfoTest.npc_relation_map("Z:\\bussiness\\Unreal\\UE_projs\\TheProject\\Content\\System\\initialRelations.csv")
changes = []
crawler = chatClass.ChatBotCrawler()

HOST = '127.0.0.1'
PORT = 7777

# Create server socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(1)
print(f"Server listening on {HOST}:{PORT}...")

conn, addr = s.accept()
print(f"Client connected from {addr}")

# response = crawler.send_message("Great. Keep this way for now. Many people used you claim that languages that make people motivated or stressed also works for you, how do u think of this case?")
# print("Bot response:", response)

# Send initial data as JSON
# conn.sendall(json.dumps(data).encode('utf-8'))
i = 1
try:
    while True:
        msg = conn.recv(4096)
        if not msg:
            print("Client disconnected.")
            break
        # print("Received from client", msg.decode('utf-8'))
        response = crawler.send_message(msg.decode('utf-8'))
        response_obj = json.loads(response)
        # print(response)
        conn.sendall(json.dumps(response_obj, ensure_ascii=False).encode('utf-8') + b'\n')

        data = json.loads(msg.decode('utf-8'))
        event = data.get("starterAndAction")
        event = "Event " + str(i) + event
        i+=1
        NPCmap, changes = NPCInfoTest.update_npc_map_with_messages(event, NPCmap, response_obj, changes)
except KeyboardInterrupt:
    print("Shutting down server.")

NPCInfoTest.store_change_history(changes)
conn.close()
s.close()
