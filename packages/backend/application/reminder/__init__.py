"""
Reminder injection service for unified status reminder management.

This module provides a centralized service for injecting system status reminders
into messages, replacing scattered injection logic across ChatService and ContextManager.
"""
from backend.application.reminder.injector import ReminderInjector

__all__ = ["ReminderInjector"]
