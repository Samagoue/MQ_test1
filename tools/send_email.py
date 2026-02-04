#!/usr/bin/env python3
"""
Reusable Email Notification Utility.

A standalone email sender that can be placed in any common directory and called
from batch files, scripts, or other applications. Uses Python's built-in smtplib
with no external dependencies required.

Usage:
    python send_email.py --from sender@example.com --to recipient@example.com --subject "Subject" --body "Message"
    python send_email.py --config /path/to/smtp.ini --to user@example.com --subject "Report" --body-file message.txt
    python send_email.py --to user@example.com --subject "Report" --body "See attached" --attach report.html data.csv

Environment variables (used if command line not provided):
    SMTP_SERVER     - SMTP server hostname (default: localhost)
    SMTP_PORT       - SMTP port (default: 25)
    SMTP_USER       - Username for authentication
    SMTP_PASSWORD   - Password for authentication
    SMTP_FROM       - Default sender address
    SMTP_USE_TLS    - Use STARTTLS (true/false)
    SMTP_USE_SSL    - Use SSL/TLS (true/false)

Exit codes:
    0 - Success
    1 - Error (check stderr for details)
"""

import os
import sys
import argparse
import smtplib
import configparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional


def send_email(
    smtp_server: str,
    smtp_port: int,
    from_address: str,
    to_addresses: List[str],
    subject: str,
    body: str,
    smtp_user: Optional[str] = None,
    smtp_password: Optional[str] = None,
    use_tls: bool = False,
    use_ssl: bool = False,
    cc_addresses: Optional[List[str]] = None,
    bcc_addresses: Optional[List[str]] = None,
    attachments: Optional[List[str]] = None,
    body_html: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> bool:
    """
    Send an email via SMTP.

    Args:
        smtp_server: SMTP server hostname
        smtp_port: SMTP server port
        from_address: Sender email address
        to_addresses: List of recipient email addresses
        subject: Email subject
        body: Plain text body
        smtp_user: Username for authentication (optional)
        smtp_password: Password for authentication (optional)
        use_tls: Use STARTTLS encryption
        use_ssl: Use SSL/TLS encryption
        cc_addresses: CC recipients (optional)
        bcc_addresses: BCC recipients (optional)
        attachments: List of file paths to attach (optional)
        body_html: HTML body for multipart emails (optional)
        reply_to: Reply-To address (optional)

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Create message
        if body_html or attachments:
            msg = MIMEMultipart("mixed")

            # Add text part
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
        msg["From"] = from_address
        msg["To"] = ", ".join(to_addresses)

        if cc_addresses:
            msg["Cc"] = ", ".join(cc_addresses)
        if reply_to:
            msg["Reply-To"] = reply_to

        # Add attachments
        if attachments:
            for filepath in attachments:
                path = Path(filepath)
                if not path.exists():
                    print(f"WARNING: Attachment not found, skipping: {filepath}", file=sys.stderr)
                    continue

                with open(path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())

                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
                msg.attach(part)

        # Build recipient list
        all_recipients = list(to_addresses)
        if cc_addresses:
            all_recipients.extend(cc_addresses)
        if bcc_addresses:
            all_recipients.extend(bcc_addresses)

        # Connect and send
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)

        try:
            if use_tls:
                server.starttls()

            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            server.sendmail(from_address, all_recipients, msg.as_string())
            return True

        finally:
            server.quit()

    except smtplib.SMTPAuthenticationError as e:
        print(f"ERROR: SMTP authentication failed: {e}", file=sys.stderr)
    except smtplib.SMTPConnectError as e:
        print(f"ERROR: Could not connect to SMTP server {smtp_server}:{smtp_port}: {e}", file=sys.stderr)
    except smtplib.SMTPException as e:
        print(f"ERROR: SMTP error: {e}", file=sys.stderr)
    except ConnectionRefusedError:
        print(f"ERROR: Connection refused to {smtp_server}:{smtp_port}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}", file=sys.stderr)

    return False


def load_config(config_path: str) -> dict:
    """Load SMTP configuration from INI file."""
    config = configparser.ConfigParser()
    config.read(config_path)

    if "smtp" not in config:
        raise ValueError(f"No [smtp] section found in {config_path}")

    s = config["smtp"]
    return {
        "smtp_server": s.get("server", "localhost"),
        "smtp_port": s.getint("port", 25),
        "smtp_user": s.get("user") or s.get("username"),
        "smtp_password": s.get("password"),
        "from_address": s.get("from") or s.get("from_address"),
        "use_tls": s.getboolean("use_tls", False),
        "use_ssl": s.getboolean("use_ssl", False),
    }


def get_env_config() -> dict:
    """Load SMTP configuration from environment variables."""
    return {
        "smtp_server": os.environ.get("SMTP_SERVER", "localhost"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "25")),
        "smtp_user": os.environ.get("SMTP_USER"),
        "smtp_password": os.environ.get("SMTP_PASSWORD"),
        "from_address": os.environ.get("SMTP_FROM"),
        "use_tls": os.environ.get("SMTP_USE_TLS", "").lower() in ("true", "1", "yes"),
        "use_ssl": os.environ.get("SMTP_USE_SSL", "").lower() in ("true", "1", "yes"),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Reusable email notification utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic email
  python send_email.py --from sender@example.com --to user@example.com \\
      --subject "Hello" --body "This is a test"

  # With config file
  python send_email.py --config /path/to/smtp.ini --to user@example.com \\
      --subject "Report" --body "See attached" --attach report.pdf

  # Body from file
  python send_email.py --to user@example.com --subject "Report" --body-file summary.txt

  # Multiple recipients and attachments
  python send_email.py --to user1@example.com user2@example.com \\
      --cc manager@example.com --subject "Weekly Report" \\
      --body "Please review the attached files" --attach report.pdf data.xlsx

  # Using environment variables for SMTP config
  export SMTP_SERVER=smtp.example.com
  export SMTP_PORT=587
  export SMTP_USER=myuser
  export SMTP_PASSWORD=mypassword
  export SMTP_FROM=sender@example.com
  export SMTP_USE_TLS=true
  python send_email.py --to recipient@example.com --subject "Test" --body "Hello"
"""
    )

    # SMTP configuration
    smtp_group = parser.add_argument_group("SMTP Configuration")
    smtp_group.add_argument("--config", "-c", metavar="FILE",
        help="Path to INI config file with SMTP settings")
    smtp_group.add_argument("--server", "-s", metavar="HOST",
        help="SMTP server hostname")
    smtp_group.add_argument("--port", "-p", type=int, metavar="PORT",
        help="SMTP server port (25, 587 for TLS, 465 for SSL)")
    smtp_group.add_argument("--user", "-u", metavar="USER",
        help="SMTP username for authentication")
    smtp_group.add_argument("--password", metavar="PASS",
        help="SMTP password for authentication")
    smtp_group.add_argument("--tls", action="store_true",
        help="Use STARTTLS encryption (typically port 587)")
    smtp_group.add_argument("--ssl", action="store_true",
        help="Use SSL/TLS encryption (typically port 465)")

    # Email content
    email_group = parser.add_argument_group("Email Content")
    email_group.add_argument("--from", "-f", dest="from_addr", metavar="EMAIL",
        help="Sender email address")
    email_group.add_argument("--to", "-t", nargs="+", required=True, metavar="EMAIL",
        help="Recipient email address(es)")
    email_group.add_argument("--cc", nargs="+", metavar="EMAIL",
        help="CC recipient(s)")
    email_group.add_argument("--bcc", nargs="+", metavar="EMAIL",
        help="BCC recipient(s)")
    email_group.add_argument("--reply-to", metavar="EMAIL",
        help="Reply-To address")
    email_group.add_argument("--subject", "-S", required=True,
        help="Email subject line")
    email_group.add_argument("--body", "-b",
        help="Email body text (plain text)")
    email_group.add_argument("--body-file", "-B", metavar="FILE",
        help="Read email body from file")
    email_group.add_argument("--html", metavar="HTML",
        help="HTML body content (creates multipart email)")
    email_group.add_argument("--html-file", metavar="FILE",
        help="Read HTML body from file")
    email_group.add_argument("--attach", "-a", nargs="+", metavar="FILE",
        help="File(s) to attach")

    # Output control
    parser.add_argument("--quiet", "-q", action="store_true",
        help="Suppress success message")
    parser.add_argument("--verbose", "-v", action="store_true",
        help="Show detailed output")

    args = parser.parse_args()

    # Load configuration (priority: command line > config file > environment)
    if args.config:
        try:
            cfg = load_config(args.config)
        except Exception as e:
            print(f"ERROR: Could not load config file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        cfg = get_env_config()

    # Override with command line arguments
    if args.server:
        cfg["smtp_server"] = args.server
    if args.port:
        cfg["smtp_port"] = args.port
    if args.user:
        cfg["smtp_user"] = args.user
    if args.password:
        cfg["smtp_password"] = args.password
    if args.from_addr:
        cfg["from_address"] = args.from_addr
    if args.tls:
        cfg["use_tls"] = True
    if args.ssl:
        cfg["use_ssl"] = True

    # Validate from address
    if not cfg.get("from_address"):
        print("ERROR: Sender address required (--from, config file, or SMTP_FROM env var)", file=sys.stderr)
        sys.exit(1)

    # Get email body
    body = args.body or ""
    if args.body_file:
        try:
            body = Path(args.body_file).read_text(encoding="utf-8")
        except Exception as e:
            print(f"ERROR: Could not read body file: {e}", file=sys.stderr)
            sys.exit(1)

    if not body:
        print("ERROR: Email body required (--body or --body-file)", file=sys.stderr)
        sys.exit(1)

    # Get HTML body if provided
    body_html = args.html
    if args.html_file:
        try:
            body_html = Path(args.html_file).read_text(encoding="utf-8")
        except Exception as e:
            print(f"ERROR: Could not read HTML file: {e}", file=sys.stderr)
            sys.exit(1)

    if args.verbose:
        print(f"SMTP: {cfg['smtp_server']}:{cfg['smtp_port']}", file=sys.stderr)
        print(f"From: {cfg['from_address']}", file=sys.stderr)
        print(f"To: {', '.join(args.to)}", file=sys.stderr)
        print(f"Subject: {args.subject}", file=sys.stderr)
        if args.attach:
            print(f"Attachments: {', '.join(args.attach)}", file=sys.stderr)

    # Send email
    success = send_email(
        smtp_server=cfg["smtp_server"],
        smtp_port=cfg["smtp_port"],
        from_address=cfg["from_address"],
        to_addresses=args.to,
        subject=args.subject,
        body=body,
        smtp_user=cfg.get("smtp_user"),
        smtp_password=cfg.get("smtp_password"),
        use_tls=cfg.get("use_tls", False),
        use_ssl=cfg.get("use_ssl", False),
        cc_addresses=args.cc,
        bcc_addresses=args.bcc,
        attachments=args.attach,
        body_html=body_html,
        reply_to=args.reply_to,
    )

    if success:
        if not args.quiet:
            print(f"OK: Email sent to {', '.join(args.to)}")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
