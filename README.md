# BvvD
Discord bot for **War Thunder** servers that sends fast notifications about game news and new videos on YouTube.
Bot supports **Russian** and **English**, and lets you configure separate channels for YouTube/News pings or send everything into one channel.

## Features
- Simple channel setup
- Fast notifications for new War Thunder news
- Fast notifications for new War Thunder YouTube videos
- Russian and English support
- Full War Thunder patch notes parsing (not just a short summary)
- Separate or combined notification channels
- Settings check command to see current configured channels and roles

## Status

This is a personal learning project that is still in development.
The core bot features already work, and more improvements will be added over time.

## Notes

Built as a Discord bot project while learning Python and discord.py.
In the first 5 minutes after setting channel for News bot might send latest 5 news not in correct order (from latest to older), this is not an error and was made so that the bot knows which news is the latest. Because of that i recommend not using @everyone for pinging and not giving people ping roles until bot stops. It should not take longer than 5 mins / 5 pings.
