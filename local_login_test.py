from telethon.sync import TelegramClient

client = TelegramClient('telethon_6399938746', 39186556, 'bad5822bd103fad569f2a711e698750f')
client.connect()
sent = client.send_code_request('+998885200054')
print("Kod so'raldi, hash:", sent.phone_code_hash)
code = input("Kelgan kodni kiriting: ")
client.sign_in('+998885200054', code, phone_code_hash=sent.phone_code_hash)
print("MUVAFFAQIYATLI ULANDI!")
client.disconnect()
