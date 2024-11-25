from contextlib import asynccontextmanager

from loguru import logger as log
from nicegui import ui


def show_notification(
    message: str,
    notification_type: str = "info",
    duration: int = 5000,
    multi_line: bool = True,
    classes: str = "multi-line-notification",
):
    """
    Display a notification using NiceGUI.

    Args:
        message (str): The message to display in the notification
        notification_type (str): Type of notification ('error', 'success', 'warning', 'info')
        duration (int): Duration to show notification in milliseconds
        multi_line (bool): Whether to allow multiple lines in notification
        classes (str): CSS classes to apply to notification
    """
    try:
        # Define color based on type
        type_colors = {
            "error": "negative",
            "success": "positive",
            "warning": "warning",
            "info": "grey",
        }
        color = type_colors.get(notification_type.lower(), "grey")

        ui.notify(
            message,
            type=color,
            duration=duration,
            multi_line=multi_line,
            classes=classes,
        )
    except Exception as e:
        error_msg = f"Failed to show notification: {e!s}"
        log.error(error_msg)
        raise


@asynccontextmanager
async def button_disable_context(button: ui.button):
    """Temporarily disable a button during an operation."""
    button.disable()
    try:
        yield
    finally:
        button.enable()
