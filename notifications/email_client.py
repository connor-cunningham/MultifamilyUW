"""Email notifications — deal reports, daily digest, deal alerts."""
from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from datetime import datetime


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


class EmailClient:
    def __init__(self):
        self.from_addr = _cfg("EMAIL_FROM")
        self.password = _cfg("EMAIL_PASSWORD")
        self.smtp_host = _cfg("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(_cfg("SMTP_PORT", "587"))
        self.alert_to = _cfg("ALERT_EMAIL_TO")
        self.alert_threshold = float(_cfg("ALERT_SCORE_THRESHOLD", "7.0"))

    @property
    def configured(self) -> bool:
        return bool(self.from_addr and self.password)

    def _send(self, to: str, subject: str, html: str, attachment: Path | None = None):
        if not self.configured:
            raise RuntimeError("Email not configured — set EMAIL_FROM and EMAIL_PASSWORD in .env")

        msg = MIMEMultipart("mixed")
        msg["From"] = self.from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html"))

        if attachment and attachment.exists():
            with open(attachment, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{attachment.name}"')
            msg.attach(part)

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.from_addr, self.password)
            server.send_message(msg)

    # ── Public API ────────────────────────────────────────────────────────────

    def send_deal_report(self, to: str, prop, results, analysis, excel_path: Path | None = None):
        """Full underwriting report email with optional Excel attachment."""
        score_color = analysis.badge_color if hasattr(analysis, "badge_color") else "#f59e0b"
        html = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto">
        <h2 style="color:#1F3864">Deal Report: {prop.address}, {prop.city}, {prop.state}</h2>
        <p style="font-size:13px;color:#666">{datetime.now().strftime('%B %d, %Y')}</p>

        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#DCE6F1">
            <th style="padding:8px;text-align:left">Metric</th>
            <th style="padding:8px;text-align:right">Value</th>
          </tr>
          <tr><td style="padding:6px">Purchase Price</td><td style="text-align:right">${prop.purchase_price:,.0f}</td></tr>
          <tr style="background:#f9f9f9"><td style="padding:6px">Price / Unit</td><td style="text-align:right">${results.price_per_unit:,.0f}</td></tr>
          <tr><td style="padding:6px">Cap Rate</td><td style="text-align:right">{results.going_in_cap_rate:.2%}</td></tr>
          <tr style="background:#f9f9f9"><td style="padding:6px">DSCR Y1</td><td style="text-align:right">{results.dscr_y1:.2f}x</td></tr>
          <tr><td style="padding:6px">CoC Y1</td><td style="text-align:right">{results.coc_y1:.2%}</td></tr>
          <tr style="background:#f9f9f9"><td style="padding:6px">5yr IRR</td><td style="text-align:right">{f"{results.irr_5yr:.2%}" if results.irr_5yr else "N/A"}</td></tr>
          <tr><td style="padding:6px">Debt Yield</td><td style="text-align:right">{f"{results.debt_yield:.2%}" if results.debt_yield else "N/A"}</td></tr>
        </table>

        <div style="background:#f4f4f4;padding:12px;border-radius:6px;margin:16px 0">
          <span style="font-size:22px;font-weight:bold;color:{score_color}">
            Score: {analysis.score}/10 &nbsp;
            <span style="background:{score_color};color:white;padding:2px 8px;border-radius:4px;font-size:16px">
              {analysis.grade} — {analysis.recommendation}
            </span>
          </span>
        </div>

        {"<h3>Investment Memo</h3><p>" + analysis.memo + "</p>" if analysis.memo else ""}

        {"<h3>Strengths</h3><ul>" + "".join(f"<li>{s}</li>" for s in analysis.strengths) + "</ul>" if analysis.strengths else ""}

        {"<h3>Risks</h3><ul>" + "".join(f"<li>{r}</li>" for r in analysis.risks) + "</ul>" if analysis.risks else ""}

        {"<p style='color:#666;font-size:12px'>" + analysis.comp_context + "</p>" if analysis.comp_context else ""}

        <hr style="margin:24px 0">
        <p style="font-size:11px;color:#999">Multifamily Deal Analyzer | {prop.source.upper()}</p>
        </body></html>
        """
        subject = f"[Deal Report] {prop.address}, {prop.city} — Score {analysis.score}/10"
        self._send(to, subject, html, excel_path)

    def send_deal_alert(self, prop, results, analysis):
        """Alert email for high-scoring deals. Uses ALERT_EMAIL_TO from env."""
        if not self.alert_to:
            return
        if analysis.score < self.alert_threshold:
            return
        self.send_deal_report(self.alert_to, prop, results, analysis, None)

    def send_daily_digest(self, to: str, deals: list[dict]):
        """Top deals discovered in the last scrape, ranked by score."""
        if not deals:
            return

        rows = ""
        for i, d in enumerate(deals[:10], 1):
            score = d.get("ai_score") or d.get("score", 0)
            grade = d.get("ai_grade") or "—"
            rows += f"""
            <tr style="background:{'#f9f9f9' if i % 2 == 0 else 'white'}">
              <td style="padding:6px">{i}</td>
              <td style="padding:6px">{d.get('address','')}, {d.get('city','')}</td>
              <td style="padding:6px;text-align:center">{d.get('state','')}</td>
              <td style="padding:6px;text-align:right">{d.get('units','')}</td>
              <td style="padding:6px;text-align:right">${float(d.get('purchase_price',0)):,.0f}</td>
              <td style="padding:6px;text-align:right">{float(d.get('going_in_cap_rate',0)):.1%}</td>
              <td style="padding:6px;text-align:center;font-weight:bold">{score}/{10} {grade}</td>
            </tr>"""

        html = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:800px;margin:auto">
        <h2 style="color:#1F3864">Daily Deal Digest — {datetime.now().strftime('%B %d, %Y')}</h2>
        <p>{len(deals)} deals underwritten today. Top {min(10,len(deals))} shown below.</p>
        <table style="width:100%;border-collapse:collapse">
          <tr style="background:#1F3864;color:white">
            <th style="padding:8px">#</th>
            <th style="padding:8px;text-align:left">Address</th>
            <th style="padding:8px">State</th>
            <th style="padding:8px">Units</th>
            <th style="padding:8px">Price</th>
            <th style="padding:8px">Cap Rate</th>
            <th style="padding:8px">Score</th>
          </tr>
          {rows}
        </table>
        <hr style="margin:24px 0">
        <p style="font-size:11px;color:#999">Multifamily Deal Analyzer — Daily Digest</p>
        </body></html>
        """
        self._send(to, f"Daily Deal Digest — {datetime.now().strftime('%b %d')}", html)

    def test_connection(self) -> tuple[bool, str]:
        """Test SMTP connection. Returns (success, message)."""
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.from_addr, self.password)
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)
