from django.urls import path
from chat.views.auth_views import RegisterView, VerifyEmailView, LoginView, LogoutView
from chat.views.chat_views import ChatHomeView, CreateRoomView, FetchMessagesView, UpdateProfileView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", ChatHomeView.as_view(), name="chat_home"),
    path('create_room/', CreateRoomView.as_view(), name='create_room'),
    path('messages/<str:room_id>/', FetchMessagesView.as_view(), name='fetch_messages'),
    path('update_profile/', UpdateProfileView.as_view(), name='update_profile'),
]