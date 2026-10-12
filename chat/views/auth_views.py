import random
import logging

from django.shortcuts import render, redirect
from django.views import View
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.template.loader import render_to_string

from chat.models import User

# Setup logger
logger = logging.getLogger(__name__)


class RegisterView(View):
    template_name = "pages/register.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get("email")
        password = request.POST.get("password")
        password2 = request.POST.get("password2")

        logger.info(f"Register attempt for email: {email}")

        if password != password2:
            messages.error(request, "Passwords do not match")
            logger.warning("Password mismatch during registration")
            return redirect("register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered")
            logger.warning(f"Email {email} already exists")
            return redirect("register")

        try:
            with transaction.atomic():
                user = User.objects.create_user(email=email, username=email, password=password)
                user.is_active = False
                user.save()
                logger.info(f"User created with id: {user.id}")

                otp_code = str(random.randint(100000, 999999))
                request.session["otp_code"] = otp_code
                request.session["user_id"] = str(user.id)  # Convert UUID to string

                # Prepare email
                email_html = render_to_string(
                    "emails/verify_email.html",
                    {"user": user, "otp_code": otp_code}
                )

                send_mail(
                    "Verify your email",
                    "",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                    html_message=email_html
                )

                messages.success(request, "OTP sent to your email. Check your inbox.")
                logger.info(f"OTP sent to {email}")
                return redirect("verify_email")

        except Exception as e:
            logger.error(f"Error during registration for {email}: {str(e)}", exc_info=True)
            messages.error(request, "An error occurred. Please try again.")
            return redirect("register")


class VerifyEmailView(View):
    template_name = "pages/verify_email.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        otp_input = request.POST.get("otp")
        user_id = request.session.get("user_id")
        otp_session = request.session.get("otp_code")

        logger.info(f"Verify email attempt for user_id: {user_id}")

        if not user_id or not otp_session:
            messages.error(request, "Session expired. Please register again.")
            logger.warning("Session expired during OTP verification")
            return redirect("register")

        if otp_input == otp_session:
            try:
                with transaction.atomic():
                    user = User.objects.get(id=user_id)
                    user.is_active = True
                    user.save()

                    # Clear session
                    request.session.pop("otp_code")
                    request.session.pop("user_id")

                    messages.success(request, "Email verified! Please login.")
                    logger.info(f"Email verified for user {user.email}")
                    return redirect("login")
            except User.DoesNotExist:
                messages.error(request, "User not found.")
                logger.error(f"User with id {user_id} not found during OTP verification")
                return redirect("register")
        else:
            messages.error(request, "Invalid OTP")
            logger.warning(f"Invalid OTP for user_id: {user_id}")
            return redirect("verify_email")


class LoginView(View):
    template_name = "pages/login.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get("email")
        password = request.POST.get("password")
        logger.info(f"Login attempt for email: {email}")

        user = authenticate(request, email=email, password=password)
        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome {user.get_full_name() or user.email}")
            logger.info(f"User {email} logged in successfully")
            return redirect("chat_home")
        else:
            messages.error(request, "Invalid email or password")
            logger.warning(f"Failed login attempt for email: {email}")
            return redirect("login")


class LogoutView(View):
    def get(self, request):
        user_email = request.user.email if request.user.is_authenticated else "Anonymous"
        auth_logout(request)
        messages.success(request, "You have been logged out.")
        logger.info(f"User {user_email} logged out")
        return redirect("login")
