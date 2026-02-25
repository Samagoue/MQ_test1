"""
Email notification module for MQ CMDB pipeline.

Provides email notification functionality that can be used by the orchestrator
and other components. Supports configuration via environment variables or config file.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

# Import the standalone email sender
# This allows using the same email logic from both CLI and programmatic access
import smtplib
import configparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders


from utils.logging_config import get_logger

logger = get_logger("utils.email_notifier")


@dataclass
class EmailConfig:
    """Email configuration settings."""
    smtp_server: str = "localhost"
    smtp_port: int = 25
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_address: str = "mqcmdb@localhost"
    use_tls: bool = False
    use_ssl: bool = False
    enabled: bool = False

    # Notification recipients
    recipients_success: List[str] = field(default_factory=list)
    recipients_failure: List[str] = field(default_factory=list)
    recipients_all: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> 'EmailConfig':
        """Load configuration from environment variables."""
        config = cls()

        config.smtp_server = os.environ.get("SMTP_SERVER", "localhost")
        config.smtp_port = int(os.environ.get("SMTP_PORT", "25"))
        config.smtp_user = os.environ.get("SMTP_USER")
        config.smtp_password = os.environ.get("SMTP_PASSWORD")
        config.from_address = os.environ.get("SMTP_FROM", "mqcmdb@localhost")
        config.use_tls = os.environ.get("SMTP_USE_TLS", "").lower() in ("true", "1", "yes")
        config.use_ssl = os.environ.get("SMTP_USE_SSL", "").lower() in ("true", "1", "yes")
        config.enabled = os.environ.get("EMAIL_ENABLED", "").lower() in ("true", "1", "yes")

        # Parse recipient lists (comma-separated)
        success_list = os.environ.get("EMAIL_RECIPIENTS_SUCCESS", "")
        failure_list = os.environ.get("EMAIL_RECIPIENTS_FAILURE", "")
        all_list = os.environ.get("EMAIL_RECIPIENTS", "")

        config.recipients_success = [r.strip() for r in success_list.split(",") if r.strip()]
        config.recipients_failure = [r.strip() for r in failure_list.split(",") if r.strip()]
        config.recipients_all = [r.strip() for r in all_list.split(",") if r.strip()]

        return config

    @classmethod
    def from_file(cls, config_path: Path) -> 'EmailConfig':
        """Load configuration from INI file."""
        config = cls()

        if not config_path.exists():
            logger.warning(f"Email config file not found: {config_path}")
            return config

        parser = configparser.ConfigParser()
        parser.read(config_path)

        if "smtp" in parser:
            smtp_section = parser["smtp"]
            config.smtp_server = smtp_section.get("server", "localhost")
            config.smtp_port = smtp_section.getint("port", 25)
            config.smtp_user = smtp_section.get("user") or smtp_section.get("username")
            config.smtp_password = smtp_section.get("password")
            config.from_address = smtp_section.get("from", "mqcmdb@localhost")
            config.use_tls = smtp_section.getboolean("use_tls", False)
            config.use_ssl = smtp_section.getboolean("use_ssl", False)

        if "notifications" in parser:
            notif_section = parser["notifications"]
            config.enabled = notif_section.getboolean("enabled", False)

            success_list = notif_section.get("recipients_success", "")
            failure_list = notif_section.get("recipients_failure", "")
            all_list = notif_section.get("recipients", "")

            config.recipients_success = [r.strip() for r in success_list.split(",") if r.strip()]
            config.recipients_failure = [r.strip() for r in failure_list.split(",") if r.strip()]
            config.recipients_all = [r.strip() for r in all_list.split(",") if r.strip()]

        return config

    def get_recipients(self, is_success: bool) -> List[str]:
        """Get recipient list based on success/failure status."""
        recipients = set(self.recipients_all)
        if is_success:
            recipients.update(self.recipients_success)
        else:
            recipients.update(self.recipients_failure)
        return list(recipients)


class EmailNotifier:
    """Send email notifications for pipeline events."""

    def __init__(self, config: Optional[EmailConfig] = None, config_file: Optional[Path] = None):
        """
        Initialize email notifier.

        Args:
            config: EmailConfig object with settings
            config_file: Path to INI config file (alternative to config object)
        """
        if config:
            self.config = config
        elif config_file and config_file.exists():
            self.config = EmailConfig.from_file(config_file)
        else:
            self.config = EmailConfig.from_env()

        self._errors: List[str] = []

    @property
    def is_enabled(self) -> bool:
        """Check if email notifications are enabled."""
        return self.config.enabled

    @property
    def errors(self) -> List[str]:
        """Get list of errors from last operation."""
        return self._errors.copy()

    def send(
        self,
        subject: str,
        body: str,
        recipients: Optional[List[str]] = None,
        is_success: bool = True,
        attachments: Optional[List[Path]] = None,
        body_html: Optional[str] = None,
    ) -> bool:
        """
        Send an email notification.

        Args:
            subject: Email subject
            body: Plain text body
            recipients: Override recipient list (uses config if not provided)
            is_success: Whether this is a success or failure notification
            attachments: List of file paths to attach
            body_html: Optional HTML body

        Returns:
            True if sent successfully, False otherwise
        """
        self._errors = []

        if not self.config.enabled:
            logger.debug("Email notifications disabled, skipping")
            return True

        # Get recipients
        to_addresses = recipients or self.config.get_recipients(is_success)

        if not to_addresses:
            logger.warning("No email recipients configured")
            self._errors.append("No recipients configured")
            return False

        logger.info(f"Sending email to {len(to_addresses)} recipient(s): {subject}")

        try:
            # Create message
            if body_html or attachments:
                msg = MIMEMultipart("mixed")

                if body_html:
                    alt_part = MIMEMultipart("alternative")
                    alt_part.attach(MIMEText(body, "plain", "utf-8"))
                    alt_part.attach(MIMEText(body_html, "html", "utf-8"))
                    msg.attach(alt_part)
                else:
                    msg.attach(MIMEText(body, "plain", "utf-8"))
            else:
                msg = MIMEText(body, "plain", "utf-8")

            # Set headers
            msg["Subject"] = subject
            msg["From"] = self.config.from_address
            msg["To"] = ", ".join(to_addresses)

            # Add attachments
            if attachments:
                for filepath in attachments:
                    if not filepath.exists():
                        logger.warning(f"Attachment not found: {filepath}")
                        continue

                    with open(filepath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())

                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f'attachment; filename="{filepath.name}"')
                    msg.attach(part)

            # Connect and send
            if self.config.use_ssl:
                server = smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port, timeout=30)

            try:
                if self.config.use_tls:
                    server.starttls()

                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)

                server.sendmail(self.config.from_address, to_addresses, msg.as_string())
                logger.info(f"Email sent successfully to {', '.join(to_addresses)}")
                return True

            finally:
                server.quit()

        except smtplib.SMTPAuthenticationError as e:
            error = f"SMTP authentication failed: {e}"
            logger.error(error)
            self._errors.append(error)
        except smtplib.SMTPConnectError as e:
            error = f"Could not connect to SMTP server {self.config.smtp_server}:{self.config.smtp_port}: {e}"
            logger.error(error)
            self._errors.append(error)
        except smtplib.SMTPException as e:
            error = f"SMTP error: {e}"
            logger.error(error)
            self._errors.append(error)
        except ConnectionRefusedError:
            error = f"Connection refused to {self.config.smtp_server}:{self.config.smtp_port}"
            logger.error(error)
            self._errors.append(error)
        except Exception as e:
            error = f"Failed to send email: {e}"
            logger.error(error)
            self._errors.append(error)

        return False

    def send_pipeline_notification(
        self,
        success: bool,
        summary: Dict[str, Any],
        log_file: Optional[Path] = None,
        error_message: Optional[str] = None,
        report_file: Optional[Path] = None,
    ) -> bool:
        """
        Send a pipeline completion notification.

        Args:
            success: Whether the pipeline succeeded
            summary: Dictionary with pipeline statistics
            log_file: Path to log file to attach
            error_message: Error message if pipeline failed
            report_file: Path to consolidated HTML report to attach

        Returns:
            True if sent successfully
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if success:
            subject = f"[MQ CMDB] Pipeline Completed Successfully - {timestamp}"
            status_text = "COMPLETED SUCCESSFULLY"
        else:
            subject = f"[MQ CMDB] Pipeline FAILED - {timestamp}"
            status_text = "FAILED"

        # Build body
        body_lines = [
            "=" * 60,
            f"MQ CMDB PIPELINE STATUS: {status_text}",
            "=" * 60,
            "",
            f"Timestamp: {timestamp}",
            "",
        ]

        if error_message:
            body_lines.extend([
                "ERROR:",
                "-" * 40,
                error_message,
                "-" * 40,
                "",
            ])

        if summary:
            body_lines.extend([
                "SUMMARY:",
                "-" * 40,
            ])
            for key, value in summary.items():
                body_lines.append(f"  {key}: {value}")
            body_lines.append("")

        if log_file and log_file.exists():
            body_lines.extend([
                f"Log file: {log_file}",
                "",
            ])

        body_lines.extend([
            "=" * 60,
            "MQ CMDB Automation System",
            "=" * 60,
        ])

        body = "\n".join(body_lines)

        # Build HTML body
        html_lines = [
            "<html><body style='font-family: Arial, sans-serif;'>",
            f"<h2 style='color: {'#28a745' if success else '#dc3545'};'>MQ CMDB Pipeline: {status_text}</h2>",
            f"<p><strong>Timestamp:</strong> {timestamp}</p>",
        ]

        if error_message:
            html_lines.extend([
                "<h3 style='color: #dc3545;'>Error</h3>",
                f"<pre style='background: #f8f9fa; padding: 10px; border-left: 4px solid #dc3545;'>{error_message}</pre>",
            ])

        if summary:
            html_lines.append("<h3>Summary</h3><table style='border-collapse: collapse;'>")
            for key, value in summary.items():
                html_lines.append(f"<tr><td style='padding: 4px 8px; border: 1px solid #ddd;'><strong>{key}</strong></td><td style='padding: 4px 8px; border: 1px solid #ddd;'>{value}</td></tr>")
            html_lines.append("</table>")

        html_lines.extend([
            "<hr style='margin-top: 20px;'>",
            "<p style='color: #666; font-size: 12px;'>MQ CMDB Automation System</p>",
            "</body></html>",
        ])

        body_html = "\n".join(html_lines)

        # Collect attachments
        attachments = []
        if log_file and log_file.exists():
            attachments.append(log_file)
        if report_file and report_file.exists():
            attachments.append(report_file)

        return self.send(
            subject=subject,
            body=body,
            is_success=success,
            attachments=attachments if attachments else None,
            body_html=body_html,
        )


def get_notifier(config_file: Optional[Path] = None) -> EmailNotifier:
    """
    Get a configured email notifier instance.

    Checks for config file in standard locations if not provided.

    Args:
        config_file: Optional path to config file

    Returns:
        Configured EmailNotifier instance
    """
    # Check standard config locations
    if config_file is None:
        search_paths = [
            Path("email_config.ini"),
            Path("config/email_config.ini"),
            Path.home() / ".mqcmdb" / "email_config.ini",
            Path("/etc/mqcmdb/email_config.ini"),
        ]

        # Also check environment variable
        env_config = os.environ.get("EMAIL_CONFIG_FILE")
        if env_config:
            search_paths.insert(0, Path(env_config))

        for path in search_paths:
            if path.exists():
                config_file = path
                logger.debug(f"Using email config: {config_file}")
                break

    return EmailNotifier(config_file=config_file)
