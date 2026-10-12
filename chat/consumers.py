import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from chat.models import ChatRoom, Message, User
import logging
from django.utils import timezone

logger = logging.getLogger('chat')

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        user = self.scope['user']
        logger.debug('WebSocket connect: room=%s, user=%s', self.room_id, user.email)

        await self.set_user_online_status(user, True)
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user': user.email,
                'status': 'online'
            }
        )

    async def disconnect(self, close_code):
        user = self.scope['user']
        logger.debug('WebSocket disconnect: room=%s, user=%s, code=%s', self.room_id, user.email, close_code)

        await self.set_user_online_status(user, False)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user': user.email,
                'status': 'offline'
            }
        )

    async def receive(self, text_data):
        logger.debug('WebSocket receive: room=%s, data=%s', self.room_id, text_data)
        data = json.loads(text_data)
        user = self.scope['user']

        if data.get('type') == 'ping':
            logger.debug('Received ping for room=%s', self.room_id)
            await self.send(text_data=json.dumps({'type': 'pong'}))
        elif data.get('message'):
            saved_message = await self.save_message(user, data['message'])
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_id': str(saved_message.id),
                    'message': data['message'],
                    'user': user.email,
                    'timestamp': saved_message.created.isoformat(),
                    'room_id': self.room_id
                }
            )
        elif 'typing' in data:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'user': user.email,
                    'typing': data['typing']
                }
            )
        elif data.get('seen') and data.get('message_id'):
            await self.save_seen(data['message_id'], user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'seen_receipt',
                    'message_id': data['message_id'],
                    'user': user.email
                }
            )

    async def chat_message(self, event):
        logger.debug('Broadcasting message: room=%s, message_id=%s', self.room_id, event['message_id'])
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message_id': event['message_id'],
            'message': event['message'],
            'user': event['user'],
            'timestamp': event['timestamp'],
            'room_id': event['room_id']
        }))

    async def typing_indicator(self, event):
        logger.debug('Broadcasting typing event: room=%s, user=%s, typing=%s', self.room_id, event['user'], event['typing'])
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user': event['user'],
            'typing': event['typing']
        }))

    async def seen_receipt(self, event):
        logger.debug('Broadcasting seen receipt: room=%s, message_id=%s, user=%s', self.room_id, event['message_id'], event['user'])
        await self.send(text_data=json.dumps({
            'type': 'seen',
            'message_id': event['message_id'],
            'user': event['user']
        }))

    async def user_status(self, event):
        logger.debug('Broadcasting status update: room=%s, user=%s, status=%s', self.room_id, event['user'], event['status'])
        await self.send(text_data=json.dumps({
            'type': 'status',
            'user': event['user'],
            'status': event['status']
        }))

    @database_sync_to_async
    def save_message(self, user, message):
        logger.debug('Saving message: room=%s, user=%s, content=%s', self.room_id, user.email, message)
        room = ChatRoom.objects.get(id=self.room_id)
        return Message.objects.create(
            room=room,
            sender=user,
            content=message,
            created=timezone.now()
        )

    @database_sync_to_async
    def save_seen(self, message_id, user):
        logger.debug('Saving seen receipt: message_id=%s, user=%s', message_id, user.email)
        message = Message.objects.get(id=message_id)
        message.seen_by.add(user)

    @database_sync_to_async
    def set_user_online_status(self, user, is_online):
        logger.debug('Setting user online status: user=%s, is_online=%s', user.email, is_online)
        user.is_online = is_online
        user.save()