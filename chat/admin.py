from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from chat.models import User, ChatRoom, Message, Notification

# =========================================================
# Custom User Admin
# =========================================================
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active", "is_superuser")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "username", "profile_image")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "first_name", "last_name", "is_active", "is_staff", "is_superuser")}
        ),
    )

admin.site.register(User, UserAdmin)

# =========================================================
# ChatRoom Admin
# =========================================================
@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "is_group", "id")
    search_fields = ("name",)
    filter_horizontal = ("participants",)

# =========================================================
# Message Admin
# =========================================================
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "sender", "content", "file")
    search_fields = ("sender__email", "content")
    filter_horizontal = ("seen_by",)

# =========================================================
# Notification Admin
# =========================================================
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "is_read", "created")
    list_filter = ("is_read", "created")
    search_fields = ("user__email", "message")
