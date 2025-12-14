import os
import json
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import MessageReactions

load_dotenv()

async def get_channel_data(client, channel_list):
    results = {}
    
    for channel_identifier in channel_list:
        try:
            print(f"📊 Обрабатываем канал: {channel_identifier}")
            
            entity = await client.get_entity(channel_identifier)
            channel_username = getattr(entity, 'username', f"id_{entity.id}")
            channel_title = getattr(entity, 'title', 'Unknown')
            
            channel_data = {
                "channel_title": channel_title,
                "channel_username": channel_username,
                "subscribers_count": None,  # Оставляем пустым для ручного заполнения
                "posts": []
            }

            # Сбор постов
            post_count = 0
            async for message in client.iter_messages(entity, limit=50):
                if not message.text:
                    continue

                # Реакции
                reactions_count = 0
                if message.reactions:
                    if isinstance(message.reactions, MessageReactions):
                        for reaction in message.reactions.results:
                            reactions_count += reaction.count
                    else:
                        reactions_count = message.reactions.count

                # Комментарии
                comments = []
                try:
                    async for reply in client.iter_messages(entity, reply_to=message.id):
                        if reply.text:  # только комментарии с текстом
                            comments.append({
                                "id": reply.id,
                                "text": reply.text,
                                "date": reply.date.isoformat()
                            })
                except:
                    pass  # игнорируем ошибки при получении комментариев

                post_data = {
                    "id": message.id,
                    "text": message.text,
                    "date": message.date.isoformat(),
                    "reactions_count": reactions_count,
                    "comments_count": len(comments),
                    "comments": comments
                    # ER убран по требованию
                }
                
                channel_data["posts"].append(post_data)
                post_count += 1

            results[channel_username] = channel_data
            print(f"✅ Успешно: {channel_title} - {post_count} постов")
            
        except Exception as e:
            print(f"❌ Ошибка для {channel_identifier}: {str(e)}")
            continue

    return results

async def main():
    client = TelegramClient(
        'user_session',
        int(os.getenv('API_ID')),
        os.getenv('API_HASH')
    )
    
    await client.start(phone=os.getenv('PHONE'))
    
    # Ваши каналы
    channels = [
        'careerlaboratory',
        'bezaspera',
        'hellonewjob'
        # добавьте другие каналы
    ]
    
    print("🚀 Начинаем сбор данных...")
    
    data = await get_channel_data(client, channels)
    
    # Сохраняем результаты
    with open('telegram_data_new.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Данные сохранены в telegram_data.json")
    print(f"📈 Обработано каналов: {len(data)}")
    
    # Краткая статистика
    for channel, info in data.items():
        posts_count = len(info['posts'])
        total_reactions = sum(post['reactions_count'] for post in info['posts'])
        total_comments = sum(post['comments_count'] for post in info['posts'])
        print(f"   📊 {info['channel_title']}: {posts_count} постов, {total_reactions} реакций, {total_comments} комментариев")
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())