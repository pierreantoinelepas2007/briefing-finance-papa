#!/usr/bin/env python3
"""
Finance Newsletter — Résumé quotidien automatique
Envoie chaque matin un résumé des actualités financières par email.
Utilise Groq (gratuit) pour générer les résumés IA.
"""

import feedparser
import smtplib
from groq import Groq
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import CONFIG

# ─── Flux RSS par catégorie ────────────────────────────────────────────────────

RSS_FEEDS = {
    "📈 Marchés boursiers": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://finance.yahoo.com/rss/topstories",
    ],
    "🌍 Économie mondiale": [
        "https://www.economist.com/finance-and-economics/rss.xml",
        "https://feeds.reuters.com/reuters/UKdomesticNews",
    ],
    "₿ Crypto / Bitcoin": [
        "https://cointelegraph.com/rss",
        "https://cryptonews.com/news/feed/",
    ],
    "🏠 Immobilier / Taux": [
        "https://www.moneyvox.fr/flux/rss.php",
        "https://feeds.reuters.com/reuters/businessNews",
    ],
    "🛢️ Matières premières": [
        "https://feeds.reuters.com/reuters/commoditiesNews",
        "https://oilprice.com/rss/main",
    ],
}

# ─── Récupération des articles ─────────────────────────────────────────────────

def fetch_articles(feeds, max_per_feed=5):
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    import calendar
                    published = datetime.fromtimestamp(
                        calendar.timegm(entry.published_parsed), tz=timezone.utc
                    )
                if published and published < cutoff:
                    continue
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                if title:
                    articles.append({"title": title, "summary": summary[:400]})
        except Exception as e:
            print(f"  ⚠️  Erreur RSS ({url}): {e}")

    return articles

# ─── Résumé IA avec Groq (gratuit) ────────────────────────────────────────────

def summarize_with_groq(category, articles):
    if not articles:
        return "Aucun article disponible pour cette catégorie aujourd'hui."

    client = Groq(api_key=CONFIG["GROQ_API_KEY"])

    articles_text = "\n".join(
        f"- {a['title']}: {a['summary']}" for a in articles[:8]
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",  # modèle gratuit et puissant
        messages=[
            {
                "role": "system",
                "content": "Tu es un journaliste financier francophone expert. Tu rédiges des résumés clairs et concis pour des investisseurs particuliers."
            },
            {
                "role": "user",
                "content": f"""Voici les actualités du jour pour : {category}

{articles_text}

Rédige 3 à 5 bullet points en français, courts et percutants, sur les points les plus importants.
Commence directement par les points, sans titre ni introduction."""
            }
        ],
        max_tokens=500,
        temperature=0.5,
    )

    return response.choices[0].message.content.strip()

# ─── Construction de l'email HTML ─────────────────────────────────────────────

def build_email_html(summaries):
    today = datetime.now().strftime("%A %d %B %Y").capitalize()

    category_colors = {
        "📈 Marchés boursiers":  "#1a6b3c",
        "🌍 Économie mondiale":  "#1a4a6b",
        "₿ Crypto / Bitcoin":   "#b45309",
        "🏠 Immobilier / Taux":  "#6b1a4a",
        "🛢️ Matières premières": "#4a3b1a",
    }

    sections_html = ""
    for category, summary in summaries.items():
        color = category_colors.get(category, "#333")
        lines = [l.strip().lstrip("-•*").strip() for l in summary.split("\n") if l.strip()]
        items_html = "".join(f"<li>{line}</li>" for line in lines if line)
        sections_html += f"""
        <div style="margin-bottom:32px; border-left:4px solid {color}; padding-left:20px;">
          <h2 style="margin:0 0 12px; font-size:18px; color:{color}; font-family:'Georgia',serif;">{category}</h2>
          <ul style="margin:0; padding-left:20px; line-height:1.9; color:#2d2d2d; font-size:15px;">{items_html}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f1eb;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f1eb;padding:40px 0;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 20px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:#0d1b2a;padding:36px 40px;">
            <p style="margin:0;color:#c9a84c;font-size:11px;letter-spacing:3px;text-transform:uppercase;font-family:'Georgia',serif;">Briefing quotidien</p>
            <h1 style="margin:8px 0 0;color:#fff;font-size:28px;font-family:'Georgia',serif;font-weight:400;">Finance &amp; Marchés</h1>
            <p style="margin:10px 0 0;color:#8a9bb0;font-size:13px;">{today}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:32px 40px 8px;border-bottom:1px solid #eee;">
            <p style="margin:0;color:#666;font-size:14px;line-height:1.7;">Bonjour 👋 Voici votre résumé des marchés et de l'actualité financière du jour.</p>
          </td>
        </tr>
        <tr><td style="padding:32px 40px;">{sections_html}</td></tr>
        <tr>
          <td style="background:#f9f7f2;padding:24px 40px;border-top:1px solid #eee;">
            <p style="margin:0;color:#999;font-size:12px;line-height:1.6;">
              Résumé généré automatiquement à partir de sources publiques (Reuters, Yahoo Finance, CoinTelegraph…).<br>
              Ce contenu ne constitue pas un conseil en investissement.<br>
              <em>Généré le {datetime.now().strftime("%d/%m/%Y à %H:%M")}</em>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

# ─── Envoi de l'email ──────────────────────────────────────────────────────────

def send_email(html_content):
    today = datetime.now().strftime("%d/%m/%Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Briefing Finance — {today}"
    msg["From"]    = CONFIG["SENDER_EMAIL"]
    msg["To"]      = CONFIG["RECIPIENT_EMAIL"]
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(CONFIG["SENDER_EMAIL"], CONFIG["GMAIL_APP_PASSWORD"])
        server.sendmail(CONFIG["SENDER_EMAIL"], CONFIG["RECIPIENT_EMAIL"], msg.as_string())

    print(f"✅ Email envoyé à {CONFIG['RECIPIENT_EMAIL']}")

# ─── Programme principal ───────────────────────────────────────────────────────

def main():
    print(f"\n🗞️  Briefing Finance — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    summaries = {}
    for category, feeds in RSS_FEEDS.items():
        print(f"\n{category}")
        articles = fetch_articles(feeds)
        print(f"  → {len(articles)} articles trouvés")
        summaries[category] = summarize_with_groq(category, articles)
        print(f"  ✓ Résumé généré")

    print("\n📧 Envoi de l'email...")
    html = build_email_html(summaries)
    send_email(html)
    print("\n🎉 Newsletter envoyée avec succès !\n")

if __name__ == "__main__":
    main()
