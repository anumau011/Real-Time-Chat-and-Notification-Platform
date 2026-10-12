import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django_extensions.db.models import (
    TimeStampedModel,
    ActivatorModel,
)
from django.utils.translation import gettext_lazy as _
# =========================================================
# Base Model
# =========================================================
class ChatWaveBaseModel(TimeStampedModel, ActivatorModel):
    """
    Abstract base model for the ChatWave system.
    
    Inherits from:
    - TimeStampedModel: adds `created` and `modified` fields.
    - ActivatorModel: adds `status` (active/inactive) and `activate_date`.
    - Uses UUID as primary key.
    """
    id = models.UUIDField(
        default=uuid.uuid4,
        null=False,
        blank=False,
        unique=True,
        primary_key=True,
        editable=False
    )
    is_deleted = models.BooleanField(default=False, help_text=_("Marks the record as deleted without removing it."))
    metadata = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        help_text=_("Stores additional metadata in JSON format.")
    )

    class Meta:
        abstract = True


# =========================================================
# Custom User Manager
# =========================================================
class UserManager(BaseUserManager):
    """
    Custom user manager for ChatWave user.
    Handles user creation with email as the unique identifier.
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


# =========================================================
# User Model
# =========================================================
class User(AbstractBaseUser, PermissionsMixin, ChatWaveBaseModel):
    """
    Custom User model with profile image.
    Uses email as the unique identifier instead of username.
    """

    email = models.EmailField(
        unique=True,
        help_text="Unique email address for the user."
    )
    username = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Optional display username."
    )
    first_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="User's first name."
    )
    last_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="User's last name."
    )
    profile_image = models.ImageField(
        upload_to="profiles/",
        blank=True,
        null=True,
        help_text="Profile picture of the user."
    )

    # Required fields for Django admin
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)

    # Attach the manager
    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # required when creating a superuser

    def __str__(self):
        return self.email or f"User {self.pk}"

    def get_full_name(self):
        """Return the full name (first + last)."""
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def get_short_name(self):
        """Return the short name (first name)."""
        return self.first_name or self.email



# =========================================================
# Chat Room
# =========================================================
class ChatRoom(ChatWaveBaseModel):
    """
    Represents a chat room for either 1-to-1 or group chats.
    """
    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Optional name of the chat room (used for group chats)."
    )
    is_group = models.BooleanField(
        default=False,
        help_text="Set to True if this chat room is for group messaging."
    )
    participants = models.ManyToManyField(
        User,
        related_name="chatrooms",
        help_text="Users who are part of this chat room."
    )

    def __str__(self):
        return self.name if self.name else f"ChatRoom {self.pk}"
    
    def get_display_name(self, current_user):
        if self.name:
            return self.name
        other_user = self.participants.exclude(id=current_user.id).first()
        return other_user.get_full_name() if other_user else "No Name"


# =========================================================
# Message
# =========================================================
class Message(ChatWaveBaseModel):
    """
    Represents a message sent in a chat room.
    Supports text messages and file attachments.
    Includes read receipts through 'seen_by'.
    """
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="messages",
        help_text="The chat room where this message was sent."
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="messages",
        help_text="The user who sent this message."
    )
    content = models.TextField(
        blank=True,
        null=True,
        help_text="The text content of the message."
    )
    file = models.FileField(
        upload_to="chat_files/",
        blank=True,
        null=True,
        help_text="Optional file or image attached to the message."
    )
    seen_by = models.ManyToManyField(
        User,
        related_name="seen_messages",
        blank=True,
        help_text="Users who have seen this message (read receipts)."
    )

    def __str__(self):
        return f"Message from {self.sender} in {self.room}"


# =========================================================
# Notification
# =========================================================
class Notification(ChatWaveBaseModel):
    """
    Represents a real-time notification for a user.
    Example: 'Alice sent you a message.'
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="The user who receives this notification."
    )
    message = models.CharField(
        max_length=255,
        help_text="Short description of the notification."
    )
    link = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Optional link associated with the notification (e.g., to a chat)."
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Indicates if the notification has been read."
    )

    def __str__(self):
        return f"Notification for {self.user}: {self.message}"
