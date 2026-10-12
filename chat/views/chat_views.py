from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from chat.models import ChatRoom, Message, User
from django.db.models import Q, Count,F
import logging
from django.utils import timezone

logger = logging.getLogger('chat')

class ChatHomeView(LoginRequiredMixin, TemplateView):
    template_name = "pages/home.html"

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            user = self.request.user
            rooms = user.chatrooms.all()
            selected_room_id = request.GET.get('room') or request.session.get('selected_room_id')
            chatrooms_data = []
            for room in rooms:
                display_name = room.get_display_name(user)
                participants = [
                    {'id': str(p.id), 'email': p.email, 'first_name': p.first_name, 'last_name': p.last_name, 'profile_image': p.profile_image.url if p.profile_image else None}
                    for p in room.participants.all()
                ]
                last_message = room.messages.order_by('-created').first()
                unread_count = room.messages.filter(~Q(sender=user), ~Q(seen_by=user)).count()
                chatrooms_data.append({
                    'id': str(room.id),
                    'name': room.name,
                    'is_group': room.is_group,
                    'display_name': display_name,
                    'participants': participants,
                    'last_message': {
                        'content': last_message.content if last_message else None,
                        'created': last_message.created.isoformat() if last_message and last_message.created else None
                    },
                    'unread_count': unread_count
                })
            users_data = list(User.objects.exclude(id=user.id).values('id', 'email', 'first_name', 'last_name'))
            logger.debug('ChatHomeView AJAX: %s chatrooms, %s users, selected_room_id=%s', len(rooms), len(users_data), selected_room_id)
            return JsonResponse({
                'chatrooms': chatrooms_data,
                'users': users_data,
                'selected_room_id': selected_room_id
            })
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        rooms = user.chatrooms.all()
        selected_room_id = self.request.GET.get('room') or self.request.session.get('selected_room_id')
        if selected_room_id:
            self.request.session['selected_room_id'] = selected_room_id

        for room in rooms:
            room.display_name = room.get_display_name(user)
            room.other_user = room.participants.exclude(id=user.id).first()
            room.last_message = room.messages.order_by('-created').first()
            room.unread_count = room.messages.filter(~Q(sender=user), ~Q(seen_by=user)).count()

        context['chatrooms'] = rooms
        context['users'] = User.objects.exclude(id=user.id).values('id', 'email', 'first_name', 'last_name')
        context['selected_room_id'] = selected_room_id
        logger.debug('ChatHomeView context: %s chatrooms, %s users, selected_room_id=%s', len(rooms), len(context['users']), selected_room_id)
        return context

class CreateRoomView(LoginRequiredMixin, View):
    def post(self, request):
        user_ids = request.POST.getlist('user_ids[]')
        logger.debug('CreateRoomView: Received user_ids: %s', user_ids)
        if not user_ids:
            logger.error("No user IDs provided for room creation")
            return JsonResponse({'success': False, 'message': 'No users selected.'}, status=400)

        user_ids = [str(request.user.id)] + user_ids
        users = User.objects.filter(id__in=user_ids, is_active=True)
        if len(users) < 2:
            logger.error("Invalid or insufficient users: %s", user_ids)
            return JsonResponse({'success': False, 'message': 'Invalid users.'}, status=400)

        if len(users) == 2:
            existing_room = ChatRoom.objects.annotate(participant_count=Count('participants')).filter(
                is_group=False,
                participant_count=2,
                participants__in=[users[0]],
            ).filter(
                participants__in=[users[1]]
            )
            if existing_room.exists():
                room = existing_room.first()
                logger.info("Found existing one-on-one room %s for users %s", room.id, [u.email for u in users])
                return JsonResponse({'success': True, 'message': 'Room already exists.', 'room_id': str(room.id)})

        room = ChatRoom.objects.create(is_group=len(users) > 2)
        room.participants.set(users)
        logger.info("Created new room %s with participants %s", room.id, [u.email for u in users])
        return JsonResponse({'success': True, 'message': 'Room created successfully.', 'room_id': str(room.id)})

class FetchMessagesView(LoginRequiredMixin, View):
    def get(self, request, room_id):
        logger.debug('FetchMessagesView: Fetching messages for room %s', room_id)
        room = get_object_or_404(ChatRoom, id=room_id)
        if request.user not in room.participants.all():
            logger.warning('Unauthorized access attempt to room %s by user %s', room_id, request.user.email)
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
        messages = room.messages.all().order_by('created').values(
            'id', 'content', 'sender__email', 'sender__first_name', 'sender__last_name', 'created',
            seen_by__email=F('seen_by__email')
        )
        participants = [
            {'email': p.email, 'is_online': p.is_online, 'profile_image': p.profile_image.url if p.profile_image else None}
            for p in room.participants.all()
        ]
        logger.debug('Fetched %s messages for room %s', len(messages), room_id)
        return JsonResponse({'success': True, 'messages': list(messages), 'participants': participants})

class UpdateProfileView(LoginRequiredMixin, View):
    def post(self, request):
        logger.debug('UpdateProfileView: Received profile update request for user %s', request.user.email)
        user = request.user
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        profile_image = request.FILES.get('profile_image')

        try:
            if username:
                user.username = username
            user.first_name = first_name
            user.last_name = last_name
            if profile_image:
                user.profile_image = profile_image
            user.save()
            logger.info('Profile updated successfully for user %s', user.email)
            response_data = {
                'success': True,
                'message': 'Profile updated successfully.',
                'full_name': user.get_full_name() or user.email,
                'profile_image_url': user.profile_image.url if user.profile_image else '/static/img/avatar.png'
            }
            return JsonResponse(response_data)
        except Exception as e:
            logger.error('Error updating profile for user %s: %s', user.email, str(e))
            return JsonResponse({'success': False, 'message': 'Failed to update profile.'}, status=400)