from telethon.sync import TelegramClient

client = TelegramClient('telethon_6399938746', 39186556, 'bad5822bd103fad569f2a711e698750f')
client.connect()
password = input("2FA parolni kiriting: ")
client.sign_in(password=password)
print("MUVAFFAQIYATLI ULANDI!")
client.disconnect()
